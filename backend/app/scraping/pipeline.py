"""Save a ScrapeResult into the database.

For every scraped item:
* known offer (same store + store product id)  -> update price/stock, log changes
* new offer                                     -> match/create the Product, create the Offer
Every price or stock change also adds a PriceHistory row (that is what the charts show).
Offers that disappeared from a fully scraped category are marked inactive.
Finally the denormalised "best price" fields of every touched product are refreshed.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Offer, PriceHistory, Product, ScrapeRun, Store
from app.scraping.base import ScrapeResult
from app.scraping.matching import find_or_create_product
from app.scraping.normalize import parse_part
from app.services.alerts import evaluate_alerts

log = logging.getLogger(__name__)


def persist_result(db: Session, store: Store, result: ScrapeResult, run: ScrapeRun) -> set[int]:
    """Returns the ids of products whose price or availability changed."""
    now = datetime.now(UTC)
    existing = {o.store_sku: o for o in db.scalars(select(Offer).where(Offer.store_id == store.id))}
    changed: set[int] = set()
    touched: set[int] = set()
    seen: set[str] = set()

    for item in result.items:
        if item.store_sku in seen:
            continue
        seen.add(item.store_sku)
        offer = existing.get(item.store_sku)

        if offer is None:
            parsed = parse_part(item.title, item.category, item.brand_hint)
            if parsed is None:
                continue  # not a real part of this category (fan, USB drive, laptop RAM...)
            product, created = find_or_create_product(db, parsed, item.image_url)
            offer = Offer(
                product_id=product.id,
                store_id=store.id,
                store_sku=item.store_sku,
                url=item.url[:600],
                title=item.title[:400],
                image_url=(item.image_url or "")[:600] or None,
                category=item.category,
                price=item.price,
                old_price=item.old_price,
                in_stock=item.in_stock,
                is_active=True,
                first_seen_at=now,
                last_seen_at=now,
                price_changed_at=now,
            )
            db.add(offer)
            db.flush()
            db.add(PriceHistory(offer_id=offer.id, price=item.price, in_stock=item.in_stock, recorded_at=now))
            run.offers_created += 1
            run.products_created += int(created)
            changed.add(product.id)
            touched.add(product.id)
            continue

        price_changed = _differs(offer.price, item.price)
        stock_changed = offer.in_stock != item.in_stock
        if price_changed:
            offer.previous_price = offer.price
            offer.price = item.price
            offer.price_changed_at = now
            run.price_changes += 1
        if price_changed or stock_changed or not offer.is_active:
            db.add(PriceHistory(offer_id=offer.id, price=item.price, in_stock=item.in_stock, recorded_at=now))
            changed.add(offer.product_id)
        offer.in_stock = item.in_stock
        offer.old_price = item.old_price
        offer.title = item.title[:400]
        offer.url = item.url[:600]
        if item.image_url:
            offer.image_url = item.image_url[:600]
        offer.is_active = True
        offer.last_seen_at = now
        run.offers_updated += 1
        touched.add(offer.product_id)

    # Offers we did not see although their whole category was scraped -> no longer listed.
    for sku, offer in existing.items():
        if sku in seen or not offer.is_active or offer.category not in result.completed_categories:
            continue
        offer.is_active = False
        db.add(PriceHistory(offer_id=offer.id, price=None, in_stock=False, recorded_at=now))
        changed.add(offer.product_id)

    db.flush()
    refresh_products(db, changed | touched)
    return changed


def persist_and_alert(db: Session, store: Store, result: ScrapeResult, run: ScrapeRun) -> list[int]:
    """Save the scrape, then check every wishlist whose product changed. Returns notification ids."""
    changed = persist_result(db, store, result, run)
    notes = evaluate_alerts(db, changed)
    return [n.id for n in notes]


def _differs(old: Decimal | None, new: Decimal | None) -> bool:
    if old is None or new is None:
        return old is not new
    return abs(Decimal(old) - Decimal(new)) >= Decimal("0.001")


def refresh_products(db: Session, product_ids: set[int]) -> None:
    """Recompute best price / store / stock / offer count for the given products."""
    if not product_ids:
        return
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    for product in products:
        active = [o for o in product.offers if o.is_active and o.price is not None]
        in_stock = [o for o in active if o.in_stock]
        pool = in_stock or active
        best = min(pool, key=lambda o: o.price) if pool else None
        product.best_price = best.price if best else None
        product.best_store_id = best.store_id if best else None
        product.in_stock = bool(in_stock)
        product.offer_count = len({o.store_id for o in active})
        if in_stock:
            low = min(o.price for o in in_stock)
            if product.lowest_price_ever is None or low < product.lowest_price_ever:
                product.lowest_price_ever = low
        if not product.image_url:
            product.image_url = next((o.image_url for o in product.offers if o.image_url), None)
