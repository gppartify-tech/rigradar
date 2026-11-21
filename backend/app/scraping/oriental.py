"""Oriental Store (os-jo.com) - an OpenCart store with a custom theme.

Technique: render each category page in Chromium (Playwright), read the product
cards, then follow the <link rel="next"> tag to the next page. robots.txt allows
category pages and `?page=N` (it only disallows search/sort/filter URLs).

Card markup (simplified):
    <article class="card">
      <a class="card-im" href="PRODUCT_URL"><img src="..."></a>
      <button data-add="11021">...</button>                 <- store product id
      <div class="card-brand">ASUS</div>
      <h3 class="card-name"><a href="PRODUCT_URL" title="FULL NAME">NAME</a></h3>
      <p class="card-line">RTX 5080 · 16GB GDDR7</p>       <- short spec summary
      <div class="card-price">
        <span class="price"><small>JOD</small>2199</span> <s class="was">2399</s>
        <span class="stock">In stock</span>
      </div>
    </article>
"""
from __future__ import annotations

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

CARD_SELECTOR = "article.card"
OUT_OF_STOCK_WORDS = ("out of stock", "sold out", "pre-order", "preorder", "unavailable", "call")


def parse_category_page(html: str, category: str, base_url: str) -> tuple[list[ScrapedItem], str | None]:
    """Pure function: category page HTML -> (items, URL of the next page or None)."""
    soup = BeautifulSoup(html, "lxml")
    items: list[ScrapedItem] = []
    for card in soup.select(CARD_SELECTOR):
        link = card.select_one(".card-name a")
        if not link or not link.get("href"):
            continue
        url = strip_query(absolute(base_url, link["href"]))
        title = clean_text(link.get("title") or link.get_text())

        sku = None
        for attr in ("data-add", "data-wish", "data-compare"):
            el = card.select_one(f"[{attr}]")
            if el is not None and el.get(attr):
                sku = el[attr]
                break
        if sku is None:
            sku = url.rstrip("/").rsplit("/", 1)[-1]

        price_el = card.select_one(".card-price .price")
        price = parse_price(price_el.get_text(" ")) if price_el else None
        was = card.select_one(".card-price .was, s.was")
        old_price = parse_price(was.get_text(" ")) if was else None

        stock_el = card.select_one(".stock")
        stock_text = clean_text(stock_el.get_text()).lower() if stock_el else ""
        if not stock_text:
            in_stock = None
        else:
            in_stock = not any(word in stock_text for word in OUT_OF_STOCK_WORDS)

        img = card.select_one(".card-im img")
        brand = card.select_one(".card-brand")
        line = card.select_one(".card-line")
        items.append(
            ScrapedItem(
                store_sku=str(sku),
                title=title,
                url=url,
                category=category,
                price=price,
                old_price=old_price if old_price and price and old_price > price else None,
                in_stock=in_stock if price is not None else False,
                image_url=absolute(base_url, img.get("src")) if img is not None and img.get("src") else None,
                brand_hint=clean_text(brand.get_text()) if brand else None,
                extra={"spec_line": clean_text(line.get_text()) if line else None},
            )
        )

    next_link = soup.select_one('link[rel="next"]')
    next_url = absolute(base_url, next_link["href"]) if next_link and next_link.get("href") else None
    return items, next_url


class OrientalScraper(BaseScraper):
    slug = "oriental"
    name = "Oriental Store"
    base_url = "https://os-jo.com"
    color = "#1baf7a"  # categorical slot 3
    categories = {
        "cpu": ["/cpu-prossesors"],  # (sic) - that is the store's real URL
        "gpu": ["/graphics-cards"],
        "motherboard": ["/motherboards"],
        "ram": ["/desktop-memory"],
        "storage": ["/solid-state-drive-ssd", "/hdd-storage"],
        "psu": ["/power-supplies"],
        "case": ["/computer-cases"],
        "cooler": ["/cpu-cooler"],  # includes both air and liquid coolers
    }

    def scrape_location(self, browser: PoliteBrowser, category: str, location: str) -> list[ScrapedItem]:
        from app.config import settings

        items: list[ScrapedItem] = []
        url: str | None = f"{self.base_url}{location}"
        visited: set[str] = set()
        for _ in range(settings.scraper_max_pages_per_category):
            if not url or url in visited:
                break
            visited.add(url)
            html = browser.fetch_html(url, wait_for=CARD_SELECTOR)
            batch, url = parse_category_page(html, category, self.base_url)
            items.extend(batch)
            if not batch:
                break
        return items
