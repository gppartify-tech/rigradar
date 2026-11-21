"""Admin dashboard: scraping status, manual scrape trigger, stats."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Listing, Offer, PriceHistory, Product, ScrapeRun, Store, User, WishlistItem
from app.schemas import AdminStatsOut, ScrapeRunOut, ScrapeTriggerIn, StoreStatsOut
from app.scraping.registry import SCRAPERS
from app.security import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/stats", response_model=AdminStatsOut)
def stats(db: Session = Depends(get_db)):
    def count(model) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0

    per_store = []
    for store in db.scalars(select(Store).order_by(Store.id)):
        active, in_stock = db.execute(
            select(func.count(Offer.id), func.count(Offer.id).filter(Offer.in_stock.is_(True)))
            .where(Offer.store_id == store.id, Offer.is_active.is_(True))
        ).one()
        per_store.append(StoreStatsOut(store=store, active_offers=active, in_stock_offers=in_stock))
    return AdminStatsOut(
        users=count(User), products=count(Product), offers=count(Offer), price_points=count(PriceHistory),
        wishlist_items=count(WishlistItem), listings=count(Listing), stores=per_store,
    )


@router.get("/scrape-runs", response_model=list[ScrapeRunOut])
def scrape_runs(limit: int = 30, db: Session = Depends(get_db)):
    return db.scalars(
        select(ScrapeRun).options(selectinload(ScrapeRun.store)).order_by(ScrapeRun.started_at.desc()).limit(min(limit, 200))
    ).all()


@router.post("/scrape", status_code=202)
def trigger_scrape(body: ScrapeTriggerIn):
    """Queue a scrape on the Celery worker (needs Redis + a running worker)."""
    from app.tasks import scrape_all_stores, scrape_store

    if body.store and body.store not in SCRAPERS:
        raise HTTPException(404, f"Unknown store. Known: {', '.join(SCRAPERS)}")
    try:
        if body.store:
            task = scrape_store.delay(body.store, trigger="manual")
        else:
            task = scrape_all_stores.delay(trigger="manual")
    except Exception as exc:  # noqa: BLE001 - broker down
        raise HTTPException(503, f"Could not reach the task queue (is Redis running?): {exc}") from exc
    return {"queued": True, "task_id": task.id, "store": body.store or "all"}
