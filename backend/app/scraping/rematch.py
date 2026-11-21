"""Re-run product matching on the offers already in the database - no scraping needed.

Use it after improving normalize.py / matching.py:  python -m app.cli rematch
Products are rebuilt from scratch; wishlist items and marketplace links follow their product.
"""
from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models import Listing, Offer, PriceHistory, Product, WishlistItem
from app.scraping.matching import find_or_create_product
from app.scraping.normalize import parse_part
from app.scraping.pipeline import refresh_products


def rematch_all(db: Session) -> dict:
    old_max = db.scalar(select(func.max(Product.id))) or 0
    offers = db.scalars(select(Offer).order_by(Offer.store_id, Offer.id)).all()
    old_to_new: dict[int, int] = {}
    orphans: list[Offer] = []
    new_ids: set[int] = set()

    for offer in offers:
        parsed = parse_part(offer.title, offer.category)
        if parsed is None:
            orphans.append(offer)
            continue
        product, _ = find_or_create_product(db, parsed, offer.image_url, min_id=old_max)
        old_to_new.setdefault(offer.product_id, product.id)
        offer.product_id = product.id
        new_ids.add(product.id)
    for offer in orphans:  # titles the new rules reject - drop them with their history
        db.delete(offer)
    db.flush()

    # Move wishlist items / marketplace links to the new products (dropping duplicates).
    for item in db.scalars(select(WishlistItem).where(WishlistItem.product_id <= old_max)).all():
        target = old_to_new.get(item.product_id)
        clash = target and db.scalar(
            select(WishlistItem).where(WishlistItem.user_id == item.user_id, WishlistItem.product_id == target)
        )
        if target is None or clash:
            db.delete(item)
        else:
            item.product_id = target
    for old, new in old_to_new.items():
        db.execute(update(Listing).where(Listing.product_id == old).values(product_id=new))
    db.flush()
    db.execute(delete(Product).where(Product.id <= old_max))
    refresh_products(db, new_ids)

    # Lowest price ever, from the full history of each product's offers.
    lows = db.execute(
        select(Offer.product_id, func.min(PriceHistory.price))
        .join(PriceHistory, PriceHistory.offer_id == Offer.id)
        .where(PriceHistory.in_stock.is_(True), PriceHistory.price.is_not(None))
        .group_by(Offer.product_id)
    ).all()
    for product_id, low in lows:
        db.execute(update(Product).where(Product.id == product_id).values(lowest_price_ever=low))
    return {"offers": len(offers) - len(orphans), "dropped_offers": len(orphans), "products": len(new_ids)}
