"""Wishlist price alerts.

Called after every scrape with the products whose price/stock changed.

Rules for a wishlist item:
* target price set:   notify ONCE when the best in-stock price drops to/below the target.
                      The alert re-arms when the price rises above the target again
                      (or the user edits the target). A further drop of 3%+ below the
                      last notified price sends one more "dropped even further" note.
* no target (track):  notify when the price drops 5%+ below the last price we told
                      the user about (or the price when they added it).
* back in stock:      notify when an out-of-stock product becomes available again.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.models import Notification, Product, WishlistItem


def _money(value: Decimal | None) -> str:
    if value is None:
        return "-"
    q = Decimal(value).quantize(Decimal("0.01"))
    text = f"{q:,.2f}".rstrip("0").rstrip(".")
    return f"{settings.currency} {text}"


def _store_name(product: Product) -> str:
    return product.best_store.name if product.best_store else "a store"


def _notify(db: Session, item: WishlistItem, kind: str, title: str, body: str) -> Notification:
    note = Notification(
        user_id=item.user_id,
        kind=kind,
        title=title[:200],
        body=body,
        link=f"/product/{item.product_id}",
        product_id=item.product_id,
    )
    db.add(note)
    return note


def evaluate_item(db: Session, item: WishlistItem, now: datetime | None = None) -> list[Notification]:
    now = now or datetime.now(UTC)
    product = item.product
    price = product.best_price if product.in_stock else None
    created: list[Notification] = []

    if item.target_price is not None:
        target = Decimal(item.target_price)
        if price is not None and price <= target:
            if item.alert_armed:
                created.append(_notify(
                    db, item, "target_reached",
                    f"Target reached: {product.name}",
                    f"{product.name} is now {_money(price)} at {_store_name(product)} "
                    f"(your target: {_money(target)}).",
                ))
                item.alert_armed = False
                item.last_notified_at, item.last_notified_price = now, price
            elif item.last_notified_price and price <= Decimal(item.last_notified_price) * Decimal("0.97"):
                created.append(_notify(
                    db, item, "price_drop",
                    f"Even cheaper: {product.name}",
                    f"{product.name} dropped again to {_money(price)} at {_store_name(product)} "
                    f"(was {_money(item.last_notified_price)} when we last told you).",
                ))
                item.last_notified_at, item.last_notified_price = now, price
        elif price is not None and price > target:
            item.alert_armed = True  # price went back up -> next drop will notify again
    elif price is not None:
        reference = item.last_notified_price or item.price_when_added
        if reference and price <= Decimal(reference) * Decimal("0.95"):
            created.append(_notify(
                db, item, "price_drop",
                f"Price drop: {product.name}",
                f"{product.name} dropped from {_money(reference)} to {_money(price)} "
                f"at {_store_name(product)}.",
            ))
            item.last_notified_at, item.last_notified_price = now, price

    if item.notify_back_in_stock and item.was_in_stock is False and product.in_stock:
        created.append(_notify(
            db, item, "back_in_stock",
            f"Back in stock: {product.name}",
            f"{product.name} is available again for {_money(product.best_price)} at {_store_name(product)}.",
        ))
    item.was_in_stock = product.in_stock
    return created


def evaluate_alerts(db: Session, product_ids: set[int] | list[int]) -> list[Notification]:
    if not product_ids:
        return []
    items = db.scalars(
        select(WishlistItem)
        .where(WishlistItem.product_id.in_(list(product_ids)))
        .options(joinedload(WishlistItem.product).joinedload(Product.best_store))
    ).all()
    created: list[Notification] = []
    for item in items:
        created.extend(evaluate_item(db, item))
    db.flush()
    return created
