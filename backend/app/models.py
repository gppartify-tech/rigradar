"""Database tables (SQLAlchemy 2.x typed ORM models).

Entity overview
---------------
Store         one of the three scraped retailers
Product       a canonical part (e.g. "AMD Ryzen 7 7800X3D"), shared by all stores
Offer         one store's listing of a product: price, stock, URL
PriceHistory  every observed price/stock change of an offer (drives the charts)
User          an account
WishlistItem  a product a user tracks, optionally with a target price
Notification  in-app notification (price alerts, ...)
Listing       a marketplace ad posted by a user (used / new parts for sale)
ListingImage  photos of a marketplace ad
ScrapeRun     log row for every scraping job (shown on the admin page)
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Jordanian Dinar has 3 decimals (1 JOD = 1000 fils).
Money = Numeric(12, 3)


def _now_col(index: bool = False) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), index=index)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(60))
    bio: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(40))
    phone: Mapped[str | None] = mapped_column(String(30))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = _now_col()

    wishlist_items: Mapped[list["WishlistItem"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    listings: Mapped[list["Listing"]] = relationship(
        back_populates="seller", cascade="all, delete-orphan"
    )


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    base_url: Mapped[str] = mapped_column(String(200))
    color: Mapped[str | None] = mapped_column(String(20))
    scraping_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (Index("ix_products_category_best_price", "category", "best_price"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)
    brand: Mapped[str | None] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(300))
    # Normalised identity used to match the same part across stores (see scraping/matching.py)
    match_key: Mapped[str] = mapped_column(String(200), index=True)
    specs: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    image_url: Mapped[str | None] = mapped_column(String(600))

    # Denormalised "best offer" fields, refreshed after every scrape (fast sorting/filtering).
    best_price: Mapped[Decimal | None] = mapped_column(Money)
    best_store_id: Mapped[int | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))
    in_stock: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    offer_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    lowest_price_ever: Mapped[Decimal | None] = mapped_column(Money)

    created_at: Mapped[datetime] = _now_col()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    offers: Mapped[list["Offer"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    best_store: Mapped[Store | None] = relationship(foreign_keys=[best_store_id])


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (UniqueConstraint("store_id", "store_sku", name="uq_offer_store_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    store_sku: Mapped[str] = mapped_column(String(80))  # the store's own product id
    url: Mapped[str] = mapped_column(String(600))
    title: Mapped[str] = mapped_column(String(400))
    image_url: Mapped[str | None] = mapped_column(String(600))
    category: Mapped[str] = mapped_column(String(20))

    price: Mapped[Decimal | None] = mapped_column(Money)
    old_price: Mapped[Decimal | None] = mapped_column(Money)  # store's own "was" price
    previous_price: Mapped[Decimal | None] = mapped_column(Money)  # our last different price
    price_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    in_stock: Mapped[bool | None] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    first_seen_at: Mapped[datetime] = _now_col()
    last_seen_at: Mapped[datetime] = _now_col()

    product: Mapped[Product] = relationship(back_populates="offers")
    store: Mapped[Store] = relationship()
    history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="offer", cascade="all, delete-orphan", order_by="PriceHistory.recorded_at"
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    price: Mapped[Decimal | None] = mapped_column(Money)
    in_stock: Mapped[bool | None] = mapped_column(Boolean)
    recorded_at: Mapped[datetime] = _now_col(index=True)

    offer: Mapped[Offer] = relationship(back_populates="history")


class WishlistItem(Base):
    __tablename__ = "wishlist_items"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    target_price: Mapped[Decimal | None] = mapped_column(Money)
    notify_back_in_stock: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    price_when_added: Mapped[Decimal | None] = mapped_column(Money)
    # An alert fires once when the price crosses below the target, then "disarms" until the
    # price goes back above the target (or the user edits the target). Prevents spamming.
    alert_armed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_notified_price: Mapped[Decimal | None] = mapped_column(Money)
    was_in_stock: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _now_col()

    user: Mapped[User] = relationship(back_populates="wishlist_items")
    product: Mapped[Product] = relationship()


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = _now_col(index=True)


class Listing(Base):
    """A marketplace ad: a user selling a part (or PC) they own."""

    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(20), index=True)
    condition: Mapped[str] = mapped_column(String(20))
    price: Mapped[Decimal] = mapped_column(Money)
    negotiable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    city: Mapped[str | None] = mapped_column(String(40))
    # Optional link to the catalog -> lets us show "new price at stores" next to the ad.
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(10), default="active", server_default="active", index=True)
    views: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = _now_col(index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    seller: Mapped[User] = relationship(back_populates="listings")
    product: Mapped[Product | None] = relationship()
    images: Mapped[list["ListingImage"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan", order_by="ListingImage.position"
    )


class ListingImage(Base):
    __tablename__ = "listing_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)

    listing: Mapped[Listing] = relationship(back_populates="images")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|success|partial|failed
    trigger: Mapped[str] = mapped_column(String(20), default="schedule")  # schedule|manual|cli
    started_at: Mapped[datetime] = _now_col(index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_fetched: Mapped[int] = mapped_column(Integer, default=0)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    offers_created: Mapped[int] = mapped_column(Integer, default=0)
    offers_updated: Mapped[int] = mapped_column(Integer, default=0)
    price_changes: Mapped[int] = mapped_column(Integer, default=0)
    products_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    store: Mapped[Store] = relationship()
