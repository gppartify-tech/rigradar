"""Wishlist / price tracker."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Product, User, WishlistItem
from app.schemas import WishlistIn, WishlistItemOut, WishlistUpdateIn
from app.security import get_current_user
from app.services.alerts import evaluate_item

router = APIRouter(prefix="/api/wishlist", tags=["wishlist"])


def _out(item: WishlistItem) -> WishlistItemOut:
    out = WishlistItemOut.model_validate(item)
    p = item.product
    out.target_reached = bool(
        item.target_price is not None and p.in_stock and p.best_price is not None and p.best_price <= item.target_price
    )
    return out


def _load(db: Session, user: User, item_id: int) -> WishlistItem:
    item = db.scalar(
        select(WishlistItem)
        .where(WishlistItem.id == item_id, WishlistItem.user_id == user.id)
        .options(joinedload(WishlistItem.product).joinedload(Product.best_store))
    )
    if item is None:
        raise HTTPException(404, "Wishlist item not found")
    return item


@router.get("", response_model=list[WishlistItemOut])
def list_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(
        select(WishlistItem)
        .where(WishlistItem.user_id == user.id)
        .options(joinedload(WishlistItem.product).joinedload(Product.best_store))
        .order_by(WishlistItem.created_at.desc())
    ).all()
    return [_out(i) for i in items]


@router.post("", response_model=WishlistItemOut, status_code=status.HTTP_201_CREATED)
def add_to_wishlist(body: WishlistIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.get(Product, body.product_id)
    if product is None:
        raise HTTPException(404, "Product not found")
    item = db.scalar(
        select(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.product_id == product.id)
    )
    if item is None:
        item = WishlistItem(
            user_id=user.id,
            product_id=product.id,
            price_when_added=product.best_price if product.in_stock else None,
            was_in_stock=product.in_stock,
        )
        db.add(item)
    item.target_price = body.target_price
    item.notify_back_in_stock = body.notify_back_in_stock
    item.alert_armed = True
    db.flush()
    db.refresh(item)
    evaluate_item(db, item, datetime.now(UTC))  # target may already be reached -> notify now
    db.commit()
    return _out(_load(db, user, item.id))


@router.patch("/{item_id}", response_model=WishlistItemOut)
def update_wishlist_item(
    item_id: int, body: WishlistUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    item = _load(db, user, item_id)
    fields = body.model_fields_set
    if "target_price" in fields:
        item.target_price = body.target_price
        item.alert_armed = True  # new target -> alert can fire again
    if "notify_back_in_stock" in fields and body.notify_back_in_stock is not None:
        item.notify_back_in_stock = body.notify_back_in_stock
    evaluate_item(db, item)
    db.commit()
    return _out(_load(db, user, item_id))


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_from_wishlist(item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _load(db, user, item_id)
    db.delete(item)
    db.commit()
