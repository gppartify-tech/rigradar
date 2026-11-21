"""Marketplace: users list their own (new or used) items for sale."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import Listing, ListingImage, Product, User
from app.schemas import (
    ListingIn,
    ListingOut,
    ListingPage,
    ListingSummaryOut,
    ListingUpdateIn,
    ProductSummaryOut,
    SellerContactOut,
)
from app.security import get_current_user, get_optional_user
from app.services.uploads import delete_upload, save_image

router = APIRouter(prefix="/api/listings", tags=["marketplace"])


def _summary(listing: Listing) -> ListingSummaryOut:
    out = ListingSummaryOut.model_validate(listing)
    out.cover_image = listing.images[0].url if listing.images else None
    return out


def _detail(listing: Listing, viewer: User | None) -> ListingOut:
    out = ListingOut.model_validate(
        {**_summary(listing).model_dump(), "description": listing.description, "views": listing.views,
         "updated_at": listing.updated_at, "images": listing.images,
         "product": ProductSummaryOut.model_validate(listing.product) if listing.product else None}
    )
    if viewer is not None:  # contact details only for logged-in users
        out.seller_contact = SellerContactOut(email=listing.seller.email, phone=listing.seller.phone)
    return out


def _load(db: Session, listing_id: int) -> Listing:
    listing = db.scalar(
        select(Listing).where(Listing.id == listing_id).options(
            selectinload(Listing.images), selectinload(Listing.seller),
            selectinload(Listing.product).selectinload(Product.best_store),
        ).execution_options(populate_existing=True)  # always fresh data after a change
    )
    if listing is None:
        raise HTTPException(404, "Listing not found")
    return listing


def _own(db: Session, listing_id: int, user: User) -> Listing:
    listing = _load(db, listing_id)
    if listing.seller_id != user.id and not user.is_admin:
        raise HTTPException(403, "This is not your listing")
    return listing


@router.get("", response_model=ListingPage)
def browse_listings(
    q: str | None = Query(None, max_length=100),
    category: str | None = None,
    condition: str | None = None,
    city: str | None = None,
    seller: str | None = Query(None, description="username"),
    product_id: int | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    status_: str = Query("active", alias="status"),
    sort: str = Query("newest", pattern="^(newest|price_asc|price_desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=60),
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
):
    stmt = select(Listing).join(User, User.id == Listing.seller_id)
    # Sold/hidden ads are only listed for their owner (profile page "sold" tab is public for sold).
    if status_ == "all" and viewer and seller and viewer.username.lower() == seller.lower():
        pass
    elif status_ in ("active", "sold"):
        stmt = stmt.where(Listing.status == status_)
    else:
        stmt = stmt.where(Listing.status == "active")
    if q:
        for token in q.lower().split()[:8]:
            like = f"%{token}%"
            stmt = stmt.where(or_(func.lower(Listing.title).like(like), func.lower(Listing.description).like(like)))
    if category:
        stmt = stmt.where(Listing.category == category)
    if condition:
        stmt = stmt.where(Listing.condition == condition)
    if city:
        stmt = stmt.where(Listing.city == city)
    if seller:
        stmt = stmt.where(func.lower(User.username) == seller.lower())
    if product_id:
        stmt = stmt.where(Listing.product_id == product_id)
    if min_price is not None:
        stmt = stmt.where(Listing.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Listing.price <= max_price)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {"price_asc": Listing.price.asc(), "price_desc": Listing.price.desc()}.get(sort, Listing.created_at.desc())
    rows = db.scalars(
        stmt.options(selectinload(Listing.images), selectinload(Listing.seller))
        .order_by(order, Listing.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ListingPage(items=[_summary(r) for r in rows], total=total, page=page, page_size=page_size,
                       pages=max(1, math.ceil(total / page_size)))


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: Session = Depends(get_db), viewer: User | None = Depends(get_optional_user)):
    listing = _load(db, listing_id)
    is_owner = viewer is not None and (viewer.id == listing.seller_id or viewer.is_admin)
    if listing.status == "hidden" and not is_owner:
        raise HTTPException(404, "Listing not found")
    if not is_owner:
        db.execute(update(Listing).where(Listing.id == listing.id).values(views=Listing.views + 1))
        db.commit()
        db.refresh(listing)
    return _detail(listing, viewer)


@router.post("", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(body: ListingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if body.product_id is not None and db.get(Product, body.product_id) is None:
        raise HTTPException(422, "Linked product does not exist")
    listing = Listing(seller_id=user.id, **body.model_dump())
    if listing.city is None:
        listing.city = user.city
    db.add(listing)
    db.commit()
    return _detail(_load(db, listing.id), user)


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int, body: ListingUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    listing = _own(db, listing_id, user)
    data = body.model_dump(exclude_unset=True)
    if data.get("product_id") is not None and db.get(Product, data["product_id"]) is None:
        raise HTTPException(422, "Linked product does not exist")
    for key, value in data.items():
        if key in ("title", "category", "condition", "price") and value is None:
            continue  # required fields can't be cleared
        setattr(listing, key, value)
    db.commit()
    return _detail(_load(db, listing_id), user)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_listing(listing_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = _own(db, listing_id, user)
    for image in listing.images:
        delete_upload(image.url)
    db.delete(listing)
    db.commit()


@router.post("/{listing_id}/images", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def upload_listing_image(
    listing_id: int, file: UploadFile = File(...), user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    listing = _own(db, listing_id, user)
    if len(listing.images) >= settings.max_images_per_listing:
        raise HTTPException(400, f"A listing can have at most {settings.max_images_per_listing} photos")
    url = save_image(file, f"listings/{listing.id}")
    listing.images.append(ListingImage(url=url, position=len(listing.images)))
    db.commit()
    return _detail(_load(db, listing_id), user)


@router.delete("/{listing_id}/images/{image_id}", response_model=ListingOut)
def delete_listing_image(
    listing_id: int, image_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    listing = _own(db, listing_id, user)
    image = next((i for i in listing.images if i.id == image_id), None)
    if image is None:
        raise HTTPException(404, "Image not found")
    delete_upload(image.url)
    listing.images.remove(image)  # delete-orphan cascade removes the row
    for position, remaining in enumerate(listing.images):
        remaining.position = position
    db.commit()
    return _detail(_load(db, listing_id), user)
