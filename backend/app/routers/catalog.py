"""Public catalog API: categories, product search/filters, product pages, price history, deals."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.constants import CATEGORIES, CONDITIONS, JORDAN_CITIES, LISTING_CATEGORIES
from app.database import get_db
from app.models import Listing, Offer, PriceHistory, Product, Store, User, WishlistItem
from app.schemas import (
    CategoryOut,
    DealOut,
    FacetsOut,
    FacetValue,
    OfferOut,
    PriceHistoryOut,
    PricePoint,
    PriceSeries,
    ProductDetailOut,
    ProductPage,
    ProductSummaryOut,
    StoreOut,
)
from app.security import get_optional_user
from app.services.catalog import FACET_SPECS, SORTS, apply_sort, build_product_query, with_store

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/meta")
def meta():
    """Static vocabularies the frontend needs (categories, cities, conditions...)."""
    return {
        "app_name": settings.app_name,
        "currency": settings.currency,
        "categories": [{"slug": k, **v} for k, v in CATEGORIES.items()],
        "listing_categories": [{"slug": k, "name": v} for k, v in LISTING_CATEGORIES.items()],
        "conditions": [{"slug": k, "name": v} for k, v in CONDITIONS.items()],
        "cities": list(JORDAN_CITIES),
        "chat_ai_enabled": bool(settings.anthropic_api_key),
    }


@router.get("/stores", response_model=list[StoreOut])
def list_stores(db: Session = Depends(get_db)):
    return db.scalars(select(Store).order_by(Store.id)).all()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            Product.category,
            func.count(Product.id),
            func.count(Product.id).filter(Product.in_stock.is_(True)),
            func.min(Product.best_price).filter(Product.in_stock.is_(True)),
        )
        .where(Product.offer_count > 0)
        .group_by(Product.category)
    ).all()
    stats = {r[0]: r for r in rows}
    out = []
    for slug, meta_ in CATEGORIES.items():
        r = stats.get(slug)
        out.append(CategoryOut(
            slug=slug, name=meta_["name"], singular=meta_["singular"],
            product_count=r[1] if r else 0, in_stock_count=r[2] if r else 0,
            min_price=float(r[3]) if r and r[3] is not None else None,
        ))
    return out


def _spec_filters(request: Request) -> dict[str, list[str]]:
    """Query params like ?spec_socket=AM5&spec_socket=AM4&spec_vram_gb=16"""
    out: dict[str, list[str]] = {}
    for key in request.query_params:
        if key.startswith("spec_"):
            out[key[5:]] = request.query_params.getlist(key)
    return out


@router.get("/products", response_model=ProductPage)
def search_products(
    request: Request,
    category: str | None = None,
    q: str | None = Query(None, max_length=100),
    brand: list[str] | None = Query(None),
    store: list[str] | None = Query(None),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    in_stock: bool = False,
    sort: str = Query("price_asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=60),
    db: Session = Depends(get_db),
):
    if category and category not in CATEGORIES:
        raise HTTPException(404, "Unknown category")
    if sort not in SORTS:
        raise HTTPException(422, f"sort must be one of {SORTS}")
    stmt = build_product_query(
        category=category, q=q, brands=brand, stores=store, min_price=min_price,
        max_price=max_price, in_stock=in_stock, specs=_spec_filters(request),
    )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        with_store(apply_sort(stmt, sort, category)).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ProductPage(
        items=[ProductSummaryOut.model_validate(p) for p in rows], total=total, page=page,
        page_size=page_size, pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/products/facets", response_model=FacetsOut)
def product_facets(category: str, db: Session = Depends(get_db)):
    if category not in CATEGORIES:
        raise HTTPException(404, "Unknown category")
    base = select(Product).where(Product.category == category, Product.offer_count > 0).subquery()
    brands = db.execute(
        select(base.c.brand, func.count()).where(base.c.brand.is_not(None))
        .group_by(base.c.brand).order_by(func.count().desc())
    ).all()
    store_rows = db.execute(
        select(Store.slug, func.count(func.distinct(Offer.product_id)))
        .join(Offer, Offer.store_id == Store.id)
        .where(Offer.category == category, Offer.is_active.is_(True))
        .group_by(Store.slug)
    ).all()
    specs: dict[str, list[FacetValue]] = {}
    for key in FACET_SPECS.get(category, []):
        value = base.c.specs[key].astext
        rows = db.execute(
            select(value, func.count()).where(value.is_not(None)).group_by(value).order_by(func.count().desc())
        ).all()
        vals = [FacetValue(value=v, count=c) for v, c in rows]
        if vals and all(v.value.replace(".", "", 1).isdigit() for v in vals):
            vals.sort(key=lambda fv: float(fv.value))
        specs[key] = vals
    prices = db.execute(select(func.min(base.c.best_price), func.max(base.c.best_price))).one()
    return FacetsOut(
        brands=[FacetValue(value=b, count=c) for b, c in brands],
        stores=[FacetValue(value=s, count=c) for s, c in store_rows],
        specs=specs,
        price_min=float(prices[0]) if prices[0] is not None else None,
        price_max=float(prices[1]) if prices[1] is not None else None,
    )


@router.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product(
    product_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)
):
    product = db.scalar(
        select(Product).where(Product.id == product_id)
        .options(selectinload(Product.offers).selectinload(Offer.store), selectinload(Product.best_store))
    )
    if product is None:
        raise HTTPException(404, "Product not found")
    offers = sorted(
        product.offers,
        key=lambda o: (not o.is_active, not o.in_stock, o.price is None, o.price or 0),
    )
    wishlist = None
    if user is not None:
        wishlist = db.scalar(
            select(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.product_id == product.id)
        )
    market = db.scalar(
        select(func.count(Listing.id)).where(Listing.product_id == product.id, Listing.status == "active")
    )
    data = ProductSummaryOut.model_validate(product).model_dump()
    return ProductDetailOut(
        **data,
        offers=[OfferOut.model_validate(o) for o in offers],
        created_at=product.created_at,
        updated_at=product.updated_at,
        wishlist=wishlist,
        marketplace_count=market or 0,
    )


@router.get("/products/{product_id}/history", response_model=PriceHistoryOut)
def price_history(product_id: int, days: int = Query(90, ge=1, le=3650), db: Session = Depends(get_db)):
    """One series per store. A store can list the same product twice (e.g. boxed and tray),
    so a store's price at any moment is its cheapest in-stock offer (else its cheapest listed one)."""
    offers = db.scalars(
        select(Offer).where(Offer.product_id == product_id).options(selectinload(Offer.store))
    ).all()
    if not offers:
        raise HTTPException(404, "Product not found")
    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    by_store: dict[int, list[Offer]] = {}
    for offer in offers:
        by_store.setdefault(offer.store_id, []).append(offer)

    series = []
    for store_offers in by_store.values():
        rows = db.execute(
            select(PriceHistory.recorded_at, PriceHistory.offer_id, PriceHistory.price, PriceHistory.in_stock)
            .where(PriceHistory.offer_id.in_([o.id for o in store_offers]))
            .order_by(PriceHistory.recorded_at, PriceHistory.id)
        ).all()
        state: dict[int, tuple] = {}
        points: list[PricePoint] = []
        for recorded_at, offer_id, price, in_stock in rows:
            state[offer_id] = (price, in_stock)
            listed = [(p, s) for p, s in state.values() if p is not None]
            available = [p for p, s in listed if s]
            value = min(available) if available else (min(p for p, _ in listed) if listed else None)
            point = PricePoint(t=recorded_at, price=_f(value), in_stock=bool(available))
            if points and points[-1].t == recorded_at:
                points[-1] = point  # several offers updated in the same scrape
            elif not points or (points[-1].price, points[-1].in_stock) != (point.price, point.in_stock):
                points.append(point)
        before = [p for p in points if p.t < since]
        window = [p for p in points if p.t >= since]
        if before:  # carry the last known price into the window
            window.insert(0, PricePoint(t=since, price=before[-1].price, in_stock=before[-1].in_stock))
        if window and any(o.is_active for o in store_offers):  # extend the line up to "now"
            window.append(PricePoint(t=now, price=window[-1].price, in_stock=window[-1].in_stock))
        if window:
            series.append(PriceSeries(store=store_offers[0].store, points=window))
    series.sort(key=lambda s: s.store.id)
    return PriceHistoryOut(product_id=product_id, series=series)


def _f(value):
    return float(value) if value is not None else None


@router.get("/products/{product_id}/similar", response_model=list[ProductSummaryOut])
def similar_products(product_id: int, limit: int = Query(8, le=20), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    stmt = select(Product).where(
        Product.category == product.category, Product.id != product.id,
        Product.offer_count > 0, Product.in_stock.is_(True),
    )
    order = []
    for key in ("chip", "socket", "memory_type", "storage_type"):  # same GPU chip / socket first
        if key in (product.specs or {}):
            order.append((Product.specs[key].astext == str(product.specs[key])).desc())
            break
    if product.best_price:
        price = float(product.best_price)
        stmt = stmt.where(Product.best_price.between(price * 0.7, price * 1.3))
        order.append(func.abs(Product.best_price - product.best_price))
    return db.scalars(with_store(stmt.order_by(*order, Product.id).limit(limit))).all()


@router.get("/deals", response_model=list[DealOut])
def deals(limit: int = Query(12, le=50), category: str | None = None, db: Session = Depends(get_db)):
    """Biggest discounts: our own tracked drops (last 14 days) + the stores' sale prices."""
    since = datetime.now(UTC) - timedelta(days=14)
    stmt = (
        select(Offer)
        .where(Offer.is_active.is_(True), Offer.in_stock.is_(True), Offer.price.is_not(None))
        .where(
            ((Offer.previous_price > Offer.price) & (Offer.price_changed_at >= since))
            | (Offer.old_price > Offer.price)
        )
        .options(selectinload(Offer.store), selectinload(Offer.product).selectinload(Product.best_store))
    )
    if category:
        stmt = stmt.where(Offer.category == category)
    candidates = []
    for offer in db.scalars(stmt):
        options = []
        if offer.previous_price and offer.previous_price > offer.price and offer.price_changed_at and offer.price_changed_at >= since:
            options.append(("price_drop", offer.previous_price))
        if offer.old_price and offer.old_price > offer.price:
            options.append(("store_sale", offer.old_price))
        kind, ref = max(options, key=lambda kr: kr[1])
        pct = float((ref - offer.price) / ref * 100)
        if pct >= 2:
            candidates.append((pct, kind, ref, offer))
    candidates.sort(key=lambda c: c[0], reverse=True)
    out, seen = [], set()
    for pct, kind, ref, offer in candidates:
        if offer.product_id in seen:
            continue
        seen.add(offer.product_id)
        out.append(DealOut(
            product=ProductSummaryOut.model_validate(offer.product), store=offer.store,
            price=float(offer.price), reference_price=float(ref), drop_pct=round(pct, 1),
            kind=kind, changed_at=offer.price_changed_at,
        ))
        if len(out) >= limit:
            break
    return out
