"""Parsers (on real saved store pages), robots.txt rules, title normalisation and matching."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.scraping import compujordan, igeek, oriental
from app.scraping.base import parse_price, strip_query
from app.scraping.matching import words_match
from app.scraping.normalize import detect_brand, parse_part
from app.scraping.robots import RobotsRules

FIXTURES = Path(__file__).parent / "fixtures"


# ----------------------------------------------------------------------------- helpers
@pytest.mark.parametrize("text, expected", [
    ("JOD 1,599.00", Decimal("1599.00")), ("JOD 27.00", Decimal("27.00")), ("2199", Decimal("2199")),
    ("0.000", None), ("", None), (None, None), ("Call for price", None),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_strip_query():
    assert strip_query("https://compujordan.com/x/item?limit=100") == "https://compujordan.com/x/item"


# ----------------------------------------------------------------------------- parsers
def test_compujordan_parser():
    html = (FIXTURES / "compujordan_category.html").read_text(encoding="utf-8")
    items, pages = compujordan.parse_category_page(html, "gpu", "https://compujordan.com")
    assert pages == 1
    assert len(items) == 6
    first = items[0]
    assert first.store_sku == "2911"
    assert first.title.startswith("ARKTEK Cyclops GeForce GT 610")
    assert first.price == Decimal("39.00") and first.in_stock is True
    assert "?" not in first.url  # tracking/limit query removed
    sale = items[1]
    assert sale.price == Decimal("379.00") and sale.old_price == Decimal("419.00")
    assert items[2].in_stock is False  # "Out Of Stock" label
    assert items[-1].in_stock is None  # neither a button nor a label


def test_oriental_parser():
    html = (FIXTURES / "oriental_category.html").read_text(encoding="utf-8")
    items, next_url = oriental.parse_category_page(html, "cpu", "https://os-jo.com")
    assert next_url == "https://os-jo.com/cpu-prossesors?page=2"
    assert len(items) == 5
    assert all(i.price and i.in_stock for i in items)
    assert items[0].brand_hint == "AMD"
    assert items[0].old_price is not None and items[0].old_price > items[0].price


def test_igeek_parser():
    data = json.loads((FIXTURES / "igeek_collection.json").read_text(encoding="utf-8"))
    items = igeek.parse_products_json(data, "cpu", "https://igeekjo.com")
    assert len(items) == 5
    assert items[0].price == Decimal("269.000") and items[0].in_stock
    assert items[0].url.startswith("https://igeekjo.com/products/")
    assert items[2].in_stock is False  # available: false
    showroom = items[3]  # price 0.000 = "showroom only"
    assert showroom.price is None and showroom.in_stock is False
    assert items[4].old_price is None  # bogus compare_at_price lower than the price is ignored


# ----------------------------------------------------------------------------- robots.txt
ROBOTS = """
User-agent: Amazonbot
Disallow: /

User-agent: *
Disallow: /admin/
Disallow: */search?*
Disallow: /*?page=
Allow: /*?page=1$
Disallow: /checkout$
"""


@pytest.mark.parametrize("url, allowed", [
    ("https://x.jo/graphics-cards", True),
    ("https://x.jo/admin/login", False),
    ("https://x.jo/index.php/search?q=rtx", False),
    ("https://x.jo/gpus?page=2", False),
    ("https://x.jo/gpus?page=1", True),       # longer Allow rule wins
    ("https://x.jo/checkout", False),
    ("https://x.jo/checkout/step2", True),    # "$" anchors the end
])
def test_robots_rules(url, allowed):
    assert RobotsRules(ROBOTS).can_fetch("PartifyBot", url) is allowed


def test_robots_named_group_overrides_star():
    rules = RobotsRules(ROBOTS)
    assert rules.can_fetch("Amazonbot", "https://x.jo/graphics-cards") is False


# ----------------------------------------------------------------------------- normalisation
@pytest.mark.parametrize("title, key, specs", [
    ("AMD Ryzen 7 7800X3D Processor – 8 Cores, 96MB Cache, Up to 5.0GHz, AM5, Tray",
     "cpu|amd|ryzen 7 7800x3d", {"socket": "AM5", "cores": 8, "packaging": "Tray"}),
    ("Intel Core i7-14700KF – 14th Gen Unlocked CPU Processor, 20 Cores",
     "cpu|intel|core i7-14700kf", {"socket": "LGA1700", "igpu": False}),
    ("Intel Core Ultra 5 250KF Plus Processor (Series 2) LGA1851",
     "cpu|intel|core ultra 5 250kf plus", {"socket": "LGA1851"}),
])
def test_parse_cpu(title, key, specs):
    part = parse_part(title, "cpu")
    assert part.key == key
    for k, v in specs.items():
        assert part.specs[k] == v


def test_parse_gpu_variants():
    a = parse_part("ASUS TUF Gaming GeForce RTX 4060 Ti 8GB GDDR6 OC Edition", "gpu")
    b = parse_part("ASUS TUF-RTX4060TI-O8G-GAMING", "gpu")
    assert a.key == "gpu|asus|rtx 4060 ti|8"
    assert a.specs["chip"] == "RTX 4060 Ti" and a.specs["score"] > 0
    assert b.specs["chip"] == "RTX 4060 Ti"
    bare = parse_part("Msi Nvidia Geforce 1650 Super 4gb Ventus Xs Oc Gddr6", "gpu")
    assert bare.specs["chip"] == "GTX 1650 Super"
    assert "mod:max" in parse_part("GIGABYTE GeForce RTX 5060 EAGLE MAX OC 8GB", "gpu").flags


def test_parse_motherboard():
    part = parse_part("MSI PRO B760M-A WIFI DDR4 Motherboard", "motherboard")
    assert part.specs["socket"] == "LGA1700" and part.specs["memory_type"] == "DDR4"
    assert part.specs["form_factor"] == "Micro-ATX" and part.specs["wifi"] is True
    am5 = parse_part("ASUS TUF GAMING B650-PLUS", "motherboard")
    assert am5.specs["memory_type"] == "DDR5" and am5.specs["form_factor"] == "ATX"


def test_parse_ram_storage_psu_case_cooler():
    ram = parse_part("G.Skill Trident Z5 RGB 32GB (2x16GB) DDR5 6000MHz CL30", "ram")
    assert ram.brand == "G.Skill"
    assert (ram.specs["capacity_gb"], ram.specs["modules"], ram.specs["speed_mhz"]) == (32, 2, 6000)
    ssd = parse_part("Samsung 990 PRO 2TB PCIe 4.0 NVMe M.2 SSD", "storage")
    assert ssd.specs["storage_type"] == "NVMe SSD" and ssd.specs["capacity_gb"] == 2000
    sata = parse_part("Kingston 1024G SSD KC600 SATA3 2.5\"", "storage")
    assert sata.specs["storage_type"] == "SATA SSD" and sata.specs["capacity_gb"] == 1000
    psu = parse_part("Corsair RM850e 850W 80 PLUS Gold Fully Modular", "psu")
    assert psu.specs["wattage"] == 850 and psu.specs["efficiency"] == "80+ Gold" and psu.specs["modular"] == "Full"
    case = parse_part("Jonsbo D31 Mini-ITX Case", "case")
    assert case.specs["supports"] == ["Mini-ITX"]
    aio = parse_part("NZXT Kraken Elite 360 RGB All-In-One 360mm Liquid CPU Cooler", "cooler")
    assert aio.specs["cooler_type"] == "Liquid" and aio.specs["radiator_mm"] == 360


@pytest.mark.parametrize("title, category", [
    ("Kingston XS1000 1TB External Portable SSD USB-C", "storage"),
    ("Kingston FURY 16GB DDR5 SODIMM Laptop Memory", "ram"),
    ("Lian Li UNI Fan CL Wireless 120 - Triple Pack", "cooler"),
    ("Thermal Grizzly Kryonaut Thermal Paste 1g", "cooler"),
    ("APC Back-UPS 650VA UPS", "psu"),
])
def test_non_parts_are_rejected(title, category):
    assert parse_part(title, category) is None


def test_brand_detection_ignores_socket_mentions():
    assert detect_brand("Arctic Freezer 36 for Intel & AMD", "cooler") == "Arctic"
    assert detect_brand("ASUS ROG Strix GeForce RTX 5080", "gpu") == "ASUS"


def test_words_match_rules():
    assert words_match("tuf oc", "tuf", 85)[0] is True           # one store omits "OC"
    assert words_match("oc", "windforce oc", 85)[0] is False     # "OC" alone says nothing
    assert words_match("prime", "tuf", 85)[0] is False


def test_same_part_from_two_stores_has_same_identity():
    a = parse_part("ASUS PRIME GeForce RTX 5060 8GB GDDR7 OC Edition Graphics Card – DLSS 4", "gpu")
    b = parse_part("ASUS PRIME GeForce RTX 5060 OC Edition 8GB GDDR7 - Graphics Card", "gpu")
    assert a.key == b.key and a.codes == b.codes and a.flags == b.flags
    assert words_match(a.words, b.words, 85)[0]
    c = parse_part("Lian Li LANCOOL 3 Mesh Mid Tower Case", "case")
    d = parse_part("Lian Li LANCOOL II Mesh C Mid-Tower Case", "case")
    assert c.codes != d.codes  # Lancool 3 is not Lancool II
