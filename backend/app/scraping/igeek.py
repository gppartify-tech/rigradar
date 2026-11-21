"""iGeek Megastore (igeekjo.com) - a Shopify store.

Technique: Shopify exposes every collection as a public JSON feed:
    https://igeekjo.com/collections/<handle>/products.json?limit=250&page=N
That gives clean structured data (title, vendor, price, availability) with no HTML
parsing at all - the easiest and most robust kind of scraping. robots.txt allows it.
"""
from __future__ import annotations

from app.scraping.base import BaseScraper, PoliteBrowser, ScrapedItem, clean_text, parse_price

PAGE_SIZE = 250


def parse_products_json(data: dict, category: str, base_url: str) -> list[ScrapedItem]:
    """Pure function: Shopify products.json -> ScrapedItems."""
    items: list[ScrapedItem] = []
    for product in data.get("products", []):
        variants = product.get("variants") or []
        if not variants:
            continue
        available = [v for v in variants if v.get("available")]
        pool = available or variants
        # cheapest variant that has a real price (0.000 = "showroom only" / call for price)
        priced = [(parse_price(str(v.get("price"))), v) for v in pool]
        priced = [(p, v) for p, v in priced if p is not None]
        price, variant = min(priced, key=lambda pv: pv[0]) if priced else (None, pool[0])

        old_price = parse_price(str(variant.get("compare_at_price") or ""))
        if old_price is not None and (price is None or old_price <= price):
            old_price = None  # some products have a bogus compare price below the price

        images = product.get("images") or []
        title = clean_text(product.get("title"))
        items.append(
            ScrapedItem(
                store_sku=str(product["id"]),
                title=title,
                url=f"{base_url}/products/{product['handle']}",
                category=category,
                price=price,
                old_price=old_price,
                in_stock=bool(available) and price is not None,
                image_url=images[0].get("src") if images else None,
                brand_hint=clean_text(product.get("vendor")) or None,
                extra={"product_type": product.get("product_type"), "tags": product.get("tags", [])},
            )
        )
    return items


class IGeekScraper(BaseScraper):
    slug = "igeek"
    name = "iGeek Megastore"
    base_url = "https://igeekjo.com"
    color = "#2a78d6"  # categorical slot 1 (validated palette)
    # The "pcb-*" collections are iGeek's own PC-builder categories (cleanly sorted);
    # the second handle adds anything that only appears in the general collection.
    categories = {
        "cpu": ["pcb-cpu", "processors-1"],
        "gpu": ["pcb-gpu", "graphic-cards-1"],
        "motherboard": ["pcb-motherboard", "motherboards-1"],
        "ram": ["pcb-ram"],
        "storage": ["pcb-storage", "internal-storage"],
        "psu": ["pcb-psu", "power-supply"],
        "case": ["pcb-case"],
        "cooler": ["pcb-cooler"],
    }

    def scrape_location(self, browser: PoliteBrowser, category: str, location: str) -> list[ScrapedItem]:
        from app.config import settings

        items: list[ScrapedItem] = []
        for page in range(1, settings.scraper_max_pages_per_category + 1):
            url = f"{self.base_url}/collections/{location}/products.json?limit={PAGE_SIZE}&page={page}"
            data = browser.fetch_json(url)
            batch = parse_products_json(data, category, self.base_url)
            items.extend(batch)
            if len(data.get("products", [])) < PAGE_SIZE:
                break
        return items

