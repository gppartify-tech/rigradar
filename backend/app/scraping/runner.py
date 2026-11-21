"""Run one store's scraper end-to-end. Used by the Celery task AND the CLI."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select

from app.database import session_scope
from app.models import ScrapeRun, Store
from app.scraping.base import PoliteBrowser
from app.scraping.pipeline import persist_and_alert
from app.scraping.registry import SCRAPERS, get_scraper

log = logging.getLogger(__name__)


def ensure_stores(db) -> dict[str, Store]:
    """Create the Store rows for every registered scraper (idempotent)."""
    stores = {s.slug: s for s in db.scalars(select(Store))}
    for slug, cls in SCRAPERS.items():
        if slug not in stores:
            store = Store(slug=slug, name=cls.name, base_url=cls.base_url, color=cls.color)
            db.add(store)
            stores[slug] = store
    db.flush()
    return stores


def run_scrape(
    store_slug: str,
    trigger: str = "manual",
    categories: list[str] | None = None,
    on_notifications: Callable[[list[int]], None] | None = None,
) -> dict:
    scraper = get_scraper(store_slug)
    with session_scope() as db:
        store = ensure_stores(db)[store_slug]
        if not store.scraping_enabled:
            return {"store": store_slug, "status": "disabled"}
        run = ScrapeRun(store_id=store.id, status="running", trigger=trigger)
        db.add(run)
        db.flush()
        run_id, store_id = run.id, store.id

    log.info("[%s] scraping started (run %s)", store_slug, run_id)
    try:
        # The slow part (minutes) happens OUTSIDE any database transaction.
        with PoliteBrowser() as browser:
            result = scraper.scrape(browser, only=categories)
    except Exception as exc:  # noqa: BLE001 - record any crash on the run
        log.exception("[%s] scraper crashed", store_slug)
        with session_scope() as db:
            run = db.get(ScrapeRun, run_id)
            run.status, run.error_message = "failed", f"{type(exc).__name__}: {exc}"[:4000]
            run.finished_at = datetime.now(UTC)
        return {"store": store_slug, "status": "failed", "error": str(exc)}

    with session_scope() as db:
        run = db.get(ScrapeRun, run_id)
        store = db.get(Store, store_id)
        note_ids = persist_and_alert(db, store, result, run)
        run.items_found = len(result.items)
        run.pages_fetched = result.pages_fetched
        if result.blocked or not result.items:
            run.status = "failed"
        else:
            run.status = "partial" if result.errors else "success"
        run.error_message = "\n".join(result.errors)[:4000] or None
        run.finished_at = datetime.now(UTC)
        store.last_scraped_at = run.finished_at
        summary = {
            "store": store_slug,
            "status": run.status,
            "items": run.items_found,
            "pages": run.pages_fetched,
            "new_offers": run.offers_created,
            "new_products": run.products_created,
            "price_changes": run.price_changes,
            "notifications": len(note_ids),
            "errors": result.errors,
        }
    if note_ids and on_notifications:
        on_notifications(note_ids)
    log.info("[%s] finished: %s", store_slug, summary)
    return summary
