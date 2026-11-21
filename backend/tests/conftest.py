"""Test setup: a separate PostgreSQL database, created fresh for every test session.

    createdb rigradar_test          (once)
    pytest                          (from the backend/ folder)

Override the database with TEST_DATABASE_URL if needed.
"""
import os
import tempfile
from decimal import Decimal

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://rigradar:rigradar@localhost:5432/rigradar_test"
)
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["SMTP_HOST"] = ""
os.environ["SEED_SAMPLE_DATA"] = "false"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="rigradar-uploads-")
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ScrapeRun  # noqa: E402
from app.scraping.base import ScrapedItem, ScrapeResult  # noqa: E402
from app.scraping.pipeline import persist_and_alert  # noqa: E402
from app.scraping.runner import ensure_stores  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        names = ", ".join(t.name for t in Base.metadata.sorted_tables)
        conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


def item(sku, title, category, price, in_stock=True, old_price=None):
    return ScrapedItem(
        store_sku=sku, title=title, url=f"https://example.com/p/{sku}", category=category,
        price=Decimal(str(price)) if price is not None else None,
        old_price=Decimal(str(old_price)) if old_price else None, in_stock=in_stock,
    )


def scrape_into(db, store_slug: str, items: list[ScrapedItem], categories=None):
    """Push fake scraped items through the real pipeline (normalise -> match -> save)."""
    stores = ensure_stores(db)
    store = stores[store_slug]
    run = ScrapeRun(store_id=store.id, status="running", trigger="cli")
    db.add(run)
    db.flush()
    result = ScrapeResult(items=items, completed_categories=set(categories or {i.category for i in items}))
    note_ids = persist_and_alert(db, store, result, run)
    db.commit()
    return note_ids


# A small but complete catalog: enough parts to build a PC.
CATALOG_IGEEK = [
    item("c1", "AMD Ryzen 5 7600 AM5 Desktop Processor (Tray) – 6 Cores", "cpu", 149),
    item("c2", "AMD Ryzen 7 7800X3D Processor – 8 Cores, 96MB Cache, AM5", "cpu", 299),
    item("c3", "Intel Core i5-14400F – 10 Cores LGA1700", "cpu", 139),
    item("g1", "ASUS Dual GeForce RTX 5060 8GB GDDR7 OC Edition", "gpu", 469),
    item("g2", "Sapphire PULSE AMD Radeon RX 9070 XT 16GB GDDR6", "gpu", 899),
    item("m1", "MSI B650M GAMING PLUS WIFI DDR5 Motherboard", "motherboard", 129),
    item("m2", "Gigabyte B760M DS3H DDR4 LGA1700", "motherboard", 99),
    item("r1", "Corsair Vengeance 32GB (2x16GB) DDR5 6000MHz CL30", "ram", 189),
    item("r2", "Kingston FURY Beast 16GB (2x8GB) DDR4 3200MHz", "ram", 79),
    item("s1", "Kingston NV3 1TB M.2 2280 NVMe SSD", "storage", 89),
    item("p1", "Corsair RM750e 750W 80+ Gold Fully Modular Power Supply", "psu", 99),
    item("k1", "Lian Li LANCOOL 216 Mid Tower Gaming Case", "case", 85),
    item("f1", "DeepCool AK400 CPU Air Cooler", "cooler", 29),
]
CATALOG_CJ = [
    item("100", "AMD Ryzen 5 7600 Desktop Processor", "cpu", 145),
    item("101", "ASUS Dual GeForce RTX 5060 OC Edition 8GB GDDR7 - Graphics Card", "gpu", 479, in_stock=False),
    item("102", "Kingston NV3 1TB PCIe 4.0 NVMe M.2 SSD", "storage", 85),
]


@pytest.fixture
def catalog(db):
    scrape_into(db, "igeek", CATALOG_IGEEK)
    scrape_into(db, "compujordan", CATALOG_CJ)
    return db


def register(client, username="sami", email=None, password="supersecret1"):
    resp = client.post("/api/auth/register", json={
        "email": email or f"{username}@example.com", "username": username, "password": password,
    })
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
