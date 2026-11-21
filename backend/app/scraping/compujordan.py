"""CompuJordan (compujordan.com) - an OpenCart store.

Technique: render the category page in Chromium (Playwright) and read the product
cards from the HTML. OpenCart lets us ask for 100 products per page (`limit=100`),
so a whole category is usually ONE request. robots.txt allows everything except /admin/.

Card markup (simplified):
    <div class="product-thumb">
      <div class="image"><a href="..."><img src="..." alt="..."></a></div>
      <div class="caption"><h4><a href="PRODUCT_URL">NAME</a></h4></div>
      <p class="tb_label_stock_status">Out Of Stock</p>      <- only when not available
      <a onclick="cart.add('3162', '1');">Add to Cart</a>    <- only when available
      <p class="price">
        <span class="price-regular">JOD 27.00</span>          (normal price)
        <span class="price-old">JOD 419.00</span><span class="price-new">JOD 379.00</span>  (sale)
      </p>
    </div>
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.scraping.base import (
    BaseScraper,
    PoliteBrowser,
    ScrapedItem,
    absolute,
    clean_text,
    parse_price,
    strip_query,
)

_SKU_RE = re.compile(r"(?:cart|wishlist|compare)\.add\('(\d+)'")
_PAGES_RE = re.compile(r"Showing \d+ to \d+ of (\d+) \((\d+) Pages?\)")
CARD_SELECTOR = ".product-thumb"


def _price_of(node) -> str | None:
    return node.get_text("", strip=True) if node else None


def parse_category_page(html: str, category: str, base_url: str) -> tuple[list[ScrapedItem], int]:
    """Pure function: category page HTML -> (items, total number of pages)."""
    soup = BeautifulSoup(html, "lxml")
    items: list[ScrapedItem] = []
    for card in soup.select(f".tb_products {CARD_SELECTOR}") or soup.select(CARD_SELECTOR):
        link = card.select_one(".caption h4 a") or card.select_one("h4 a")
        if not link or not link.get("href"):
            continue
        url = strip_query(absolute(base_url, link["href"]))

        sku = None
        for el in card.select("[onclick]"):
            if m := _SKU_RE.search(el.get("onclick", "")):
                sku = m.group(1)
                break
        if sku is None:  # fall back to the URL slug
            sku = url.rstrip("/").rsplit("/", 1)[-1]

        new = card.select_one(".price .price-new")
        price = parse_price(_price_of(new or card.select_one(".price .price-regular")))
        old_price = parse_price(_price_of(card.select_one(".price .price-old"))) if new else None

        label = card.select_one(".tb_label_stock_status")
        if label is not None:
            in_stock = False  # "Out Of Stock" / "Pre-Order"
        elif card.select_one(".tb_button_add_to_cart"):
            in_stock = True
        else:
            in_stock = None  # no button and no label: availability unknown

        img = card.select_one(".image img")
        image = None
        if img is not None:
            image = absolute(base_url, img.get("src") or img.get("data-src"))

        items.append(
            ScrapedItem(
                store_sku=sku,
                title=clean_text(link.get_text()),
                url=url,
                category=category,
                price=price,
                old_price=old_price if old_price and price and old_price > price else None,
                in_stock=in_stock,
                image_url=image,
                extra={"stock_label": clean_text(label.get_text()) if label else None},
            )
        )

    pages = 1
    if m := _PAGES_RE.search(soup.get_text(" ")):
        pages = int(m.group(2))
    return items, pages


class CompuJordanScraper(BaseScraper):
    slug = "compujordan"
    name = "CompuJordan"
    base_url = "https://compujordan.com"
    color = "#eb6834"  # categorical slot 2
    categories = {
        "cpu": ["/computer-hardware/components/cpu"],
        "gpu": ["/computer-hardware/components/graphic-card"],
        "motherboard": ["/computer-hardware/components/motherboard"],
        "ram": ["/computer-hardware/components/memory-ram"],
        "storage": ["/gaming-rampage/gaming-components/storage-drive"],
        "psu": ["/computer-hardware/components/power-supply"],
        "case": ["/computer-hardware/components/cases"],
        "cooler": ["/computer-hardware/components/cpu-cooler"],
    }

    def scrape_location(self, browser: PoliteBrowser, category: str, location: str) -> list[ScrapedItem]:
        from app.config import settings

        items: list[ScrapedItem] = []
        page, total_pages = 1, 1
        while page <= min(total_pages, settings.scraper_max_pages_per_category):
            url = f"{self.base_url}{location}?limit=100&page={page}"
            html = browser.fetch_html(url, wait_for=CARD_SELECTOR)
            batch, total_pages = parse_category_page(html, category, self.base_url)
            items.extend(batch)
            if not batch:
                break
            page += 1
        return items
