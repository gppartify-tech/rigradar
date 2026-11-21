"""The list of stores we scrape. Add a new store = write a scraper + register it here."""
from app.scraping.base import BaseScraper
from app.scraping.compujordan import CompuJordanScraper
from app.scraping.igeek import IGeekScraper
from app.scraping.oriental import OrientalScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    cls.slug: cls for cls in (IGeekScraper, CompuJordanScraper, OrientalScraper)
}


def get_scraper(slug: str) -> BaseScraper:
    try:
        return SCRAPERS[slug]()
    except KeyError as exc:
        raise ValueError(f"Unknown store {slug!r}. Known: {', '.join(SCRAPERS)}") from exc
