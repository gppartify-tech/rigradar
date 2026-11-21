"""Pydantic schemas: the shapes of API request bodies and responses.

Prices are stored as exact decimals in PostgreSQL but sent to the browser as
plain JSON numbers (floats) because that is what JavaScript understands.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.constants import CATEGORY_SLUGS, CONDITIONS, JORDAN_CITIES, LISTING_CATEGORIES


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- users
class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=60)


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=255, description="E-mail or username")
    password: str = Field(min_length=1, max_length=128)


class PublicUserOut(ORM):
    id: int
    username: str
    display_name: str
    bio: str | None = None
    city: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class MeOut(PublicUserOut):
    email: str
    phone: str | None = None
    is_admin: bool
    email_notifications: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: MeOut


class ProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    bio: str | None = Field(default=None, max_length=1000)
    city: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=30, pattern=r"^[0-9+()\- ]*$")
    email_notifications: bool | None = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class PublicProfileOut(PublicUserOut):
    active_listings: int
    sold_listings: int


# --------------------------------------------------------------------------- catalog
class StoreOut(ORM):
    id: int
    slug: str
    name: str
    base_url: str
    color: str | None = None
    last_scraped_at: datetime | None = None


class CategoryOut(BaseModel):
    slug: str
    name: str
    singular: str
    product_count: int
    in_stock_count: int
    min_price: float | None = None


class ProductSummaryOut(ORM):
    id: int
    category: str
    brand: str | None = None
    name: str
    image_url: str | None = None
    best_price: float | None = None
    lowest_price_ever: float | None = None
    in_stock: bool
    offer_count: int
    best_store: StoreOut | None = None
    specs: dict = Field(default_factory=dict)

    @field_validator("specs", mode="before")
    @classmethod
    def _public_specs(cls, value):
        # keys starting with "_" are internal matching data (see scraping/normalize.py)
        return {k: v for k, v in (value or {}).items() if not k.startswith("_")}


class OfferOut(ORM):
    id: int
    store: StoreOut
    url: str
    title: str
    price: float | None = None
    old_price: float | None = None
    previous_price: float | None = None
    in_stock: bool | None = None
    is_active: bool
    last_seen_at: datetime
    price_changed_at: datetime | None = None


class WishlistBriefOut(ORM):
    id: int
    target_price: float | None = None
    notify_back_in_stock: bool


class ProductDetailOut(ProductSummaryOut):
    offers: list[OfferOut]
    created_at: datetime
    updated_at: datetime
    wishlist: WishlistBriefOut | None = None
    marketplace_count: int = 0


class ProductPage(BaseModel):
    items: list[ProductSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int


class FacetValue(BaseModel):
    value: str
    count: int


class FacetsOut(BaseModel):
    brands: list[FacetValue]
    stores: list[FacetValue]
    specs: dict[str, list[FacetValue]]
    price_min: float | None = None
    price_max: float | None = None


class PricePoint(BaseModel):
    t: datetime
    price: float | None
    in_stock: bool | None


class PriceSeries(BaseModel):
    """One line on the chart: a store's cheapest offer for the product over time."""
    store: StoreOut
    points: list[PricePoint]


class PriceHistoryOut(BaseModel):
    product_id: int
    series: list[PriceSeries]


class DealOut(BaseModel):
    product: ProductSummaryOut
    store: StoreOut
    price: float
    reference_price: float
    drop_pct: float
    kind: Literal["store_sale", "price_drop"]
    changed_at: datetime | None = None


# --------------------------------------------------------------------------- wishlist
class WishlistIn(BaseModel):
    product_id: int
    target_price: Decimal | None = Field(default=None, gt=0, le=100000)
    notify_back_in_stock: bool = True


class WishlistUpdateIn(BaseModel):
    # Send "target_price": null to remove the target (track only).
    target_price: Decimal | None = Field(default=None, gt=0, le=100000)
    notify_back_in_stock: bool | None = None


class WishlistItemOut(ORM):
    id: int
    product: ProductSummaryOut
    target_price: float | None = None
    notify_back_in_stock: bool
    price_when_added: float | None = None
    alert_armed: bool
    last_notified_at: datetime | None = None
    created_at: datetime
    target_reached: bool = False


# --------------------------------------------------------------------------- notifications
class NotificationOut(ORM):
    id: int
    kind: str
    title: str
    body: str
    link: str | None = None
    product_id: int | None = None
    is_read: bool
    created_at: datetime


class UnreadCountOut(BaseModel):
    unread: int


# --------------------------------------------------------------------------- marketplace
class ListingImageOut(ORM):
    id: int
    url: str
    position: int


class _ListingFields(BaseModel):
    @field_validator("category", check_fields=False)
    @classmethod
    def _check_category(cls, v):
        if v is not None and v not in LISTING_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(LISTING_CATEGORIES)}")
        return v

    @field_validator("condition", check_fields=False)
    @classmethod
    def _check_condition(cls, v):
        if v is not None and v not in CONDITIONS:
            raise ValueError(f"condition must be one of {sorted(CONDITIONS)}")
        return v

    @field_validator("city", check_fields=False)
    @classmethod
    def _check_city(cls, v):
        if v and v not in JORDAN_CITIES:
            raise ValueError("unknown city")
        return v or None


class ListingIn(_ListingFields):
    title: str = Field(min_length=5, max_length=150)
    description: str = Field(default="", max_length=5000)
    category: str
    condition: str
    price: Decimal = Field(gt=0, le=100000)
    negotiable: bool = True
    city: str | None = None
    product_id: int | None = None


class ListingUpdateIn(_ListingFields):
    title: str | None = Field(default=None, min_length=5, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = None
    condition: str | None = None
    price: Decimal | None = Field(default=None, gt=0, le=100000)
    negotiable: bool | None = None
    city: str | None = None
    product_id: int | None = None
    status: Literal["active", "sold", "hidden"] | None = None


class SellerContactOut(BaseModel):
    email: str
    phone: str | None = None


class ListingSummaryOut(ORM):
    id: int
    title: str
    category: str
    condition: str
    price: float
    negotiable: bool
    city: str | None = None
    status: str
    created_at: datetime
    cover_image: str | None = None
    seller: PublicUserOut


class ListingOut(ListingSummaryOut):
    description: str
    views: int
    updated_at: datetime
    images: list[ListingImageOut]
    product: ProductSummaryOut | None = None
    # Only filled in for logged-in viewers (keeps contact details away from scrapers).
    seller_contact: SellerContactOut | None = None


class ListingPage(BaseModel):
    items: list[ListingSummaryOut]
    total: int
    page: int
    page_size: int
    pages: int


# --------------------------------------------------------------------------- builds / recommender
UseCase = Literal["gaming", "creator", "office", "workstation", "streaming"]
Resolution = Literal["1080p", "1440p", "4k"]


class BuildCheckIn(BaseModel):
    product_ids: list[int] = Field(min_length=1, max_length=12)


class CompatIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    message: str


class BuildPartOut(BaseModel):
    category: str
    product: ProductSummaryOut
    price: float | None
    reason: str | None = None


class BuildCheckOut(BaseModel):
    parts: list[BuildPartOut]
    total_price: float
    estimated_wattage: int
    recommended_psu_w: int
    issues: list[CompatIssue]
    compatible: bool


class RecommendIn(BaseModel):
    budget: Decimal = Field(ge=150, le=20000, description="Total budget in JOD")
    use_case: UseCase = "gaming"
    resolution: Resolution | None = None
    cpu_brand: Literal["any", "amd", "intel"] = "any"
    gpu_brand: Literal["any", "nvidia", "amd", "intel"] = "any"
    # Categories to include. Leave empty for a full build.
    include: list[str] | None = None
    in_stock_only: bool = True

    @field_validator("include")
    @classmethod
    def _check_include(cls, v):
        if v:
            bad = [c for c in v if c not in CATEGORY_SLUGS]
            if bad:
                raise ValueError(f"unknown categories: {bad}")
        return v


class RecommendOut(BuildCheckOut):
    budget: float
    leftover: float
    use_case: str
    resolution: str | None = None
    notes: list[str]


# --------------------------------------------------------------------------- chat
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)


class ChatOut(BaseModel):
    reply: str
    mode: Literal["ai", "offline"]
    products: list[ProductSummaryOut] = Field(default_factory=list)
    build: RecommendOut | None = None


# --------------------------------------------------------------------------- admin
class ScrapeRunOut(ORM):
    id: int
    store: StoreOut
    status: str
    trigger: str
    started_at: datetime
    finished_at: datetime | None = None
    pages_fetched: int
    items_found: int
    offers_created: int
    offers_updated: int
    price_changes: int
    products_created: int
    error_message: str | None = None


class StoreStatsOut(BaseModel):
    store: StoreOut
    active_offers: int
    in_stock_offers: int


class AdminStatsOut(BaseModel):
    users: int
    products: int
    offers: int
    price_points: int
    wishlist_items: int
    listings: int
    stores: list[StoreStatsOut]


class ScrapeTriggerIn(BaseModel):
    store: str | None = Field(default=None, description="Store slug, or empty for all stores")
