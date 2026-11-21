"""Scrape pipeline (matching, history, stale offers) and wishlist price alerts."""
from decimal import Decimal

from sqlalchemy import func, select

from app.models import Notification, Offer, PriceHistory, Product, User, WishlistItem
from tests.conftest import item, scrape_into


def test_same_product_from_two_stores_is_merged(catalog):
    db = catalog
    r5 = db.scalar(select(Product).where(Product.match_key == "cpu|amd|ryzen 5 7600"))
    assert r5.offer_count == 2
    assert r5.best_price == Decimal("145.000")  # CompuJordan is cheaper than iGeek's 149
    gpu = db.scalar(select(Product).where(Product.match_key == "gpu|asus|rtx 5060|8"))
    assert gpu.offer_count == 2
    assert gpu.best_price == Decimal("469.000")  # the out-of-stock 479 offer is ignored
    assert gpu.in_stock is True


def test_price_change_creates_history_and_previous_price(catalog):
    db = catalog
    scrape_into(db, "compujordan", [
        item("100", "AMD Ryzen 5 7600 Desktop Processor", "cpu", 135),
        item("101", "ASUS Dual GeForce RTX 5060 OC Edition 8GB GDDR7 - Graphics Card", "gpu", 479, in_stock=False),
        item("102", "Kingston NV3 1TB PCIe 4.0 NVMe M.2 SSD", "storage", 85),
    ])
    offer = db.scalar(select(Offer).where(Offer.store_sku == "100"))
    assert offer.price == Decimal("135.000") and offer.previous_price == Decimal("145.000")
    assert db.scalar(select(func.count()).where(PriceHistory.offer_id == offer.id)) == 2
    unchanged = db.scalar(select(Offer).where(Offer.store_sku == "102"))
    assert db.scalar(select(func.count()).where(PriceHistory.offer_id == unchanged.id)) == 1


def test_offer_missing_from_complete_category_becomes_inactive(catalog):
    db = catalog
    scrape_into(db, "compujordan", [item("100", "AMD Ryzen 5 7600 Desktop Processor", "cpu", 145)],
                categories={"cpu", "gpu", "storage"})
    ssd = db.scalar(select(Offer).where(Offer.store_sku == "102"))
    assert ssd.is_active is False


def _wish(db, product, target=None, user_id=None):
    if user_id is None:
        user = User(email="w@example.com", username="w", display_name="w", password_hash="x")
        db.add(user)
        db.flush()
        user_id = user.id
    wi = WishlistItem(user_id=user_id, product_id=product.id, target_price=target,
                      price_when_added=product.best_price, was_in_stock=product.in_stock)
    db.add(wi)
    db.commit()
    return wi


def test_target_price_alert_fires_once_and_rearms(catalog):
    db = catalog
    r5 = db.scalar(select(Product).where(Product.match_key == "cpu|amd|ryzen 5 7600"))
    wi = _wish(db, r5, target=Decimal("140"))
    cpu_items = lambda price: [item("100", "AMD Ryzen 5 7600 Desktop Processor", "cpu", price)]  # noqa: E731

    scrape_into(db, "compujordan", cpu_items(139), categories=set())  # drops below target
    notes = db.scalars(select(Notification)).all()
    assert [n.kind for n in notes] == ["target_reached"]
    assert "139" in notes[0].body

    scrape_into(db, "compujordan", cpu_items(138), categories=set())  # tiny further drop: no spam
    assert db.scalar(select(func.count(Notification.id))) == 1

    scrape_into(db, "compujordan", cpu_items(150), categories=set())  # back above target (iGeek 149)
    db.refresh(wi)
    assert wi.alert_armed is True
    scrape_into(db, "compujordan", cpu_items(129), categories=set())  # below again -> second alert
    assert db.scalar(select(func.count(Notification.id))) == 2


def test_back_in_stock_alert(db):
    scrape_into(db, "igeek", [item("x1", "AMD Ryzen 9 9950X Processor", "cpu", 499, in_stock=False)])
    product = db.scalar(select(Product))
    _wish(db, product)
    scrape_into(db, "igeek", [item("x1", "AMD Ryzen 9 9950X Processor", "cpu", 489, in_stock=True)])
    kinds = [n.kind for n in db.scalars(select(Notification))]
    assert "back_in_stock" in kinds
