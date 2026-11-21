"""Seeding helpers: admin account + demo data snapshot.

The snapshot (app/data/sample_snapshot.json.gz) is a real scrape of the three stores,
so the site has realistic data the moment it starts - even with no internet, or if
a store changes its HTML right before your graduation demo :)
"""
from __future__ import annotations

import gzip
import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Offer, PriceHistory, Product, Store, User
from app.scraping.runner import ensure_stores
from app.security import hash_password

log = logging.getLogger(__name__)
SNAPSHOT_PATH = Path(__file__).parent / "data" / "sample_snapshot.json.gz"


def create_admin(db: Session, email: str, password: str, username: str = "admin") -> User:
    user = db.scalar(select(User).where((User.email == email.lower()) | (User.username == username)))
    if user is None:
        user = User(email=email.lower(), username=username, display_name="Administrator",
                    password_hash=hash_password(password), is_admin=True)
        db.add(user)
    else:
        user.is_admin = True
    db.flush()
    return user


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dec(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def export_snapshot(db: Session, path: Path = SNAPSHOT_PATH) -> dict:
    stores = {s.id: s for s in db.scalars(select(Store))}
    data = {
        "version": 1,
        "exported_at": datetime.now().isoformat(),
        "stores": [
            {"slug": s.slug, "last_scraped_at": _iso(s.last_scraped_at)} for s in stores.values()
        ],
        "products": [
            {
                "id": p.id, "category": p.category, "brand": p.brand, "name": p.name,
                "match_key": p.match_key, "specs": p.specs, "image_url": p.image_url,
                "lowest_price_ever": _dec(p.lowest_price_ever), "created_at": _iso(p.created_at),
            }
            for p in db.scalars(select(Product))
        ],
        "offers": [
            {
                "id": o.id, "product_id": o.product_id, "store": stores[o.store_id].slug,
                "store_sku": o.store_sku, "url": o.url, "title": o.title, "image_url": o.image_url,
                "category": o.category, "price": _dec(o.price), "old_price": _dec(o.old_price),
                "previous_price": _dec(o.previous_price), "price_changed_at": _iso(o.price_changed_at),
                "in_stock": o.in_stock, "is_active": o.is_active,
                "first_seen_at": _iso(o.first_seen_at), "last_seen_at": _iso(o.last_seen_at),
            }
            for o in db.scalars(select(Offer))
        ],
        "history": [
            [h.offer_id, _dec(h.price), h.in_stock, _iso(h.recorded_at)]
            for h in db.scalars(select(PriceHistory).order_by(PriceHistory.id))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    return {k: len(v) for k, v in data.items() if isinstance(v, list)}


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def import_snapshot(db: Session, path: Path = SNAPSHOT_PATH) -> dict:
    """Load the snapshot into an EMPTY catalog (no-op when products already exist)."""
    if db.scalar(select(func.count(Product.id))):
        return {"skipped": "catalog is not empty"}
    if not path.exists():
        return {"skipped": f"{path} not found"}
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)

    from app.scraping.pipeline import refresh_products

    stores = ensure_stores(db)
    for s in data["stores"]:
        if s["slug"] in stores:
            stores[s["slug"]].last_scraped_at = _dt(s["last_scraped_at"])
    product_ids: dict[int, int] = {}
    for p in data["products"]:
        product = Product(
            category=p["category"], brand=p["brand"], name=p["name"], match_key=p["match_key"],
            specs=p["specs"], image_url=p["image_url"], created_at=_dt(p["created_at"]),
            lowest_price_ever=Decimal(p["lowest_price_ever"]) if p["lowest_price_ever"] else None,
        )
        db.add(product)
        db.flush()
        product_ids[p["id"]] = product.id
    offer_ids: dict[int, int] = {}
    for o in data["offers"]:
        if o["store"] not in stores:
            continue
        offer = Offer(
            product_id=product_ids[o["product_id"]], store_id=stores[o["store"]].id,
            store_sku=o["store_sku"], url=o["url"], title=o["title"], image_url=o["image_url"],
            category=o["category"], in_stock=o["in_stock"], is_active=o["is_active"],
            price=Decimal(o["price"]) if o["price"] else None,
            old_price=Decimal(o["old_price"]) if o["old_price"] else None,
            previous_price=Decimal(o["previous_price"]) if o["previous_price"] else None,
            price_changed_at=_dt(o["price_changed_at"]), first_seen_at=_dt(o["first_seen_at"]),
            last_seen_at=_dt(o["last_seen_at"]),
        )
        db.add(offer)
        db.flush()
        offer_ids[o["id"]] = offer.id
    db.add_all(
        PriceHistory(offer_id=offer_ids[h[0]], price=Decimal(h[1]) if h[1] else None, in_stock=h[2],
                     recorded_at=_dt(h[3]))
        for h in data["history"] if h[0] in offer_ids
    )
    db.flush()
    refresh_products(db, set(product_ids.values()))
    return {"products": len(product_ids), "offers": len(offer_ids), "history": len(data["history"])}


DEMO_PASSWORD = "demo12345"
DEMO_USERS = [
    ("sami", "Sami H.", "Amman", "Upgrading to AM5, selling my old parts. Everything tested, original boxes.", [
        ("MSI RTX 3060 Ventus 2X 12GB", "gpu", "good", 165, "rtx 3060", "Used for 2 years for gaming only, never mined. Runs cool, no coil whine. Original box included."),
        ("Ryzen 5 5600 + B550M motherboard combo", "other", "good", 120, None, "AMD Ryzen 5 5600 with an MSI B550M PRO-VDH board. BIOS updated, perfect for a budget AM4 build."),
        ("Corsair Vengeance LPX 16GB (2x8) DDR4 3200", "ram", "good", 25, None, "Two sticks, XMP stable at 3200 MHz."),
    ]),
    ("lina", "Lina K.", "Irbid", "Content creator - I sell the parts I replace.", [
        ("Gaming PC: i5-12400F + RTX 3060 Ti, 16GB RAM, 1TB NVMe", "pc", "good", 520, None, "Complete tower, Windows activated, plays everything at 1080p high. Can show it running before you buy."),
        ("Samsung 970 EVO Plus 1TB NVMe", "storage", "like_new", 45, None, "95% health, moved to a 2TB drive."),
    ]),
    ("omar", "Omar N.", "Zarqa", "PC builder and tinkerer.", [
        ("ASUS TUF RTX 4070 Super OC 12GB - warranty until 2027", "gpu", "like_new", 520, "rtx 4070 super", "Bought from a local store, invoice included. Selling because I moved to a 5080."),
        ("Cooler Master MWE 650 Bronze V2", "psu", "fair", 30, None, "Works fine, fan slightly louder than new."),
    ]),
]


def seed_demo_users(db: Session) -> dict:
    """Demo accounts with marketplace listings (for presentations). Never enable in production:
    the accounts share a public password."""
    from app.models import Listing

    if db.scalar(select(func.count(Listing.id))):
        return {"skipped": "marketplace is not empty"}
    created = 0
    for username, name, city, bio, listings in DEMO_USERS:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            user = User(email=f"{username}@demo.rigradar.local", username=username, display_name=name,
                        city=city, bio=bio, password_hash=hash_password(DEMO_PASSWORD))
            db.add(user)
            db.flush()
        for title, category, condition, price, chip, description in listings:
            product_id = None
            if chip:  # link to the catalog so buyers can compare with the new price
                product_id = db.scalar(
                    select(Product.id).where(Product.category == category, Product.specs["chip"].astext.ilike(chip))
                    .order_by(Product.in_stock.desc(), Product.best_price).limit(1)
                )
            db.add(Listing(seller_id=user.id, title=title, description=description, category=category,
                           condition=condition, price=Decimal(price), city=city, product_id=product_id))
            created += 1
    db.flush()
    return {"users": len(DEMO_USERS), "listings": created, "password": DEMO_PASSWORD}


def seed(db: Session) -> dict:
    """Idempotent start-up seed: stores, optional admin, optional demo data."""
    report: dict = {"stores": len(ensure_stores(db))}
    if settings.admin_email and settings.admin_password:
        create_admin(db, settings.admin_email, settings.admin_password, settings.admin_username)
        report["admin"] = settings.admin_email
    if settings.seed_sample_data:
        report["sample_data"] = import_snapshot(db)
    if settings.seed_demo_users:
        report["demo_users"] = seed_demo_users(db)
    return report
