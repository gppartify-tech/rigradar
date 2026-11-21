"""Product search/filter helpers shared by the catalog API, the recommender and the chatbot."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Float, Select, and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.models import Offer, Product, Store

# Spec keys offered as filters for each category (in this order).
FACET_SPECS: dict[str, list[str]] = {
    "cpu": ["socket", "cores", "igpu"],
    "gpu": ["chip", "vram_gb", "chip_maker"],
    "motherboard": ["socket", "chipset", "form_factor", "memory_type", "wifi"],
    "ram": ["memory_type", "capacity_gb", "speed_mhz"],
    "storage": ["storage_type", "capacity_gb"],
    "psu": ["wattage", "efficiency", "modular"],
    "case": ["form_factor"],
    "cooler": ["cooler_type", "radiator_mm"],
}
# Which spec is the "performance" number for a category.
SCORE_SPEC = {"gpu": "score", "cpu": "gaming_score"}

SORTS = ("relevance", "price_asc", "price_desc", "name", "newest", "stores", "performance")


def spec_value_text(value) -> str:
    """How a JSON spec value looks through `specs->>key` (true/false/16/'AM5')."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_product_query(
    *,
    category: str | None = None,
    q: str | None = None,
    brands: list[str] | None = None,
    stores: list[str] | None = None,
    min_price: Decimal | float | None = None,
    max_price: Decimal | float | None = None,
    in_stock: bool | None = None,
    specs: dict[str, list[str]] | None = None,
) -> Select:
    stmt = select(Product).where(Product.offer_count > 0)
    if category:
        stmt = stmt.where(Product.category == category)
    if q:
        for token in q.lower().split()[:8]:
            like = f"%{token}%"
            stmt = stmt.where(or_(func.lower(Product.name).like(like), func.lower(Product.brand).like(like)))
    if brands:
        stmt = stmt.where(Product.brand.in_(brands))
    if stores:
        sub = (
            select(Offer.product_id)
            .join(Store, Store.id == Offer.store_id)
            .where(Store.slug.in_(stores), Offer.is_active)
        )
        stmt = stmt.where(Product.id.in_(sub))
    if min_price is not None:
        stmt = stmt.where(Product.best_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.best_price <= max_price)
    if in_stock:
        stmt = stmt.where(Product.in_stock.is_(True))
    for key, values in (specs or {}).items():
        if values:
            stmt = stmt.where(Product.specs[key].astext.in_([str(v) for v in values]))
    return stmt


def apply_sort(stmt: Select, sort: str, category: str | None = None) -> Select:
    stock_first = Product.in_stock.desc()
    if sort == "price_desc":
        return stmt.order_by(stock_first, Product.best_price.desc().nulls_last(), Product.id)
    if sort == "name":
        return stmt.order_by(Product.name, Product.id)
    if sort == "newest":
        return stmt.order_by(Product.created_at.desc(), Product.id.desc())
    if sort == "stores":
        return stmt.order_by(stock_first, Product.offer_count.desc(), Product.best_price.asc().nulls_last())
    if sort == "performance":
        key = SCORE_SPEC.get(category or "", "score")
        score = Product.specs[key].astext.cast(Float)
        return stmt.order_by(stock_first, score.desc().nulls_last(), Product.best_price.asc().nulls_last())
    if sort == "relevance":
        return stmt.order_by(stock_first, Product.offer_count.desc(), Product.best_price.asc().nulls_last())
    return stmt.order_by(stock_first, Product.best_price.asc().nulls_last(), Product.id)


def with_store(stmt: Select) -> Select:
    return stmt.options(selectinload(Product.best_store))


def offers_condition_active():
    return and_(Offer.is_active.is_(True), Offer.price.is_not(None))
