"""Shared scraping building blocks.

PoliteBrowser wraps one Playwright Chromium instance for a whole scraping run and
enforces our scraping etiquette in ONE place:

1. robots.txt is downloaded once per host and every URL is checked against it.
2. Requests to the same host are spaced out (SCRAPE_DELAY_SECONDS + a little jitter).
3. Images, fonts, media, stylesheets and third-party trackers are never downloaded,
   which keeps the load we put on the stores (and our bandwidth) small.
4. If a store answers with a bot challenge / 403 / 429 we STOP and report it -
   we never try to get around a site's protection.

Each store module only has to say *which* URLs to visit and *how* to parse them.
The parsing functions are pure (HTML/JSON in -> items out) so they can be unit
tested with saved pages, without a browser or network.
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlsplit

from app.config import settings
from app.scraping.robots import ALLOW_ALL, RobotsRules

log = logging.getLogger(__name__)

BOT_NAME = "PartifyBot"
BLOCKED_RESOURCE_TYPES = {"image", "media", "font", "stylesheet", "texttrack", "manifest"}


class ScrapeError(Exception):
    """Something went wrong fetching a page."""


class BlockedError(ScrapeError):
    """The store refused automated access (bot challenge, 403, 429, robots.txt)."""


@dataclass
class ScrapedItem:
    """One product card as seen on a store page, before matching."""

    store_sku: str  # the store's own product id
    title: str
    url: str
    category: str  # our category slug (cpu, gpu, ...)
    price: Decimal | None
    old_price: Decimal | None = None  # strike-through price shown by the store
    in_stock: bool | None = None
    image_url: str | None = None
    brand_hint: str | None = None  # brand as given by the store, if any
    extra: dict = field(default_factory=dict)


@dataclass
class ScrapeResult:
    items: list[ScrapedItem] = field(default_factory=list)
    pages_fetched: int = 0
    errors: list[str] = field(default_factory=list)
    # Categories whose pages were ALL fetched successfully. Only offers in these
    # categories may be marked "no longer listed" when they were not seen.
    completed_categories: set[str] = field(default_factory=set)
    blocked: bool = False


# --------------------------------------------------------------------------- helpers
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_price(text: str | None) -> Decimal | None:
    """'JOD 1,599.00' -> Decimal('1599.00'); returns None for empty / zero prices."""
    if not text:
        return None
    match = _NUMBER.search(text.replace(" ", " "))
    if not match:
        return None
    try:
        value = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    return value if value > 0 else None


def strip_query(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"


def absolute(base: str, url: str | None) -> str | None:
    return urljoin(base, url) if url else None


def clean_text(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


# --------------------------------------------------------------------------- browser
class PoliteBrowser:
    """Context manager around a Playwright browser with robots.txt + rate limiting."""

    def __init__(
        self,
        delay_seconds: float | None = None,
        user_agent: str | None = None,
        headless: bool | None = None,
    ):
        self.delay = settings.scrape_delay_seconds if delay_seconds is None else delay_seconds
        self.user_agent = user_agent or settings.scraper_user_agent
        self.headless = settings.scraper_headless if headless is None else headless
        self.pages_fetched = 0
        self._robots: dict[str, RobotsRules] = {}
        self._last_hit: dict[str, float] = {}
        self._pw = self._browser = self._context = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self) -> PoliteBrowser:
        from playwright.sync_api import sync_playwright  # imported lazily: heavy

        self._pw = sync_playwright().start()
        launch_kwargs: dict = {"headless": self.headless}
        if settings.playwright_chromium_path:
            launch_kwargs["executable_path"] = settings.playwright_chromium_path
        if settings.scraper_proxy:
            launch_kwargs["proxy"] = {"server": settings.scraper_proxy}
        self._browser = self._pw.chromium.launch(**launch_kwargs)
        self._context = self._browser.new_context(
            user_agent=self.user_agent,
            locale="en-US",
            viewport={"width": 1366, "height": 900},
        )
        self._context.set_default_timeout(settings.scraper_page_timeout_ms)
        return self

    def __exit__(self, *exc) -> None:
        for closer in (self._context, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass
        if self._pw:
            self._pw.stop()

    # -- etiquette -----------------------------------------------------------
    def _wait_turn(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            wait = self.delay + random.uniform(0, 0.5) - (time.monotonic() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    def robots_for(self, url: str) -> RobotsRules:
        parts = urlsplit(url)
        host = parts.netloc
        if host not in self._robots:
            robots_url = f"{parts.scheme}://{host}/robots.txt"
            try:
                self._wait_turn(host)
                resp = self._context.request.get(robots_url, timeout=20_000)
                self._robots[host] = RobotsRules(resp.text()) if resp.ok else ALLOW_ALL
                log.info("robots.txt for %s: HTTP %s", host, resp.status)
            except Exception as exc:  # noqa: BLE001
                log.warning("could not read %s (%s) - assuming allowed", robots_url, exc)
                self._robots[host] = ALLOW_ALL
        return self._robots[host]

    def _check_allowed(self, url: str) -> None:
        if not self.robots_for(url).can_fetch(BOT_NAME, url):
            raise BlockedError(f"robots.txt disallows {url}")

    # -- fetching ------------------------------------------------------------
    def fetch_json(self, url: str, retries: int = 2):
        """GET a JSON document (used for the Shopify product feed)."""
        self._check_allowed(url)
        host = urlsplit(url).netloc
        for attempt in range(retries + 1):
            self._wait_turn(host)
            try:
                resp = self._context.request.get(
                    url, headers={"Accept": "application/json"}, timeout=30_000
                )
            except Exception as exc:  # noqa: BLE001 - network error
                if attempt == retries:
                    raise ScrapeError(f"{url}: {exc}") from exc
                time.sleep(2 * (attempt + 1))
                continue
            self.pages_fetched += 1
            if resp.status in (403, 429):
                raise BlockedError(f"{url}: HTTP {resp.status}")
            if resp.status >= 500 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            if not resp.ok:
                raise ScrapeError(f"{url}: HTTP {resp.status}")
            return resp.json()
        raise ScrapeError(f"{url}: giving up")

    def fetch_html(self, url: str, wait_for: str | None = None, retries: int = 2) -> str:
        """Open a page in Chromium and return the rendered HTML."""
        self._check_allowed(url)
        site_host = urlsplit(url).netloc
        site_root = site_host.removeprefix("www.")

        def _route(route):
            req = route.request
            req_host = urlsplit(req.url).netloc
            first_party = req_host == site_host or req_host.endswith("." + site_root)
            if req.resource_type in BLOCKED_RESOURCE_TYPES or not first_party:
                return route.abort()
            return route.continue_()

        for attempt in range(retries + 1):
            self._wait_turn(site_host)
            page = self._context.new_page()
            page.route("**/*", _route)
            try:
                resp = page.goto(url, wait_until="domcontentloaded")
                self.pages_fetched += 1
                status = resp.status if resp else 0
                title = page.title()
                if status in (403, 429) or "just a moment" in title.lower():
                    raise BlockedError(f"{url}: blocked (HTTP {status}, title {title!r})")
                if status >= 500:
                    raise ScrapeError(f"{url}: HTTP {status}")
                if status == 404:
                    raise ScrapeError(f"{url}: HTTP 404 (category moved?)")
                if wait_for:
                    try:
                        page.wait_for_selector(wait_for, timeout=15_000)
                    except Exception:  # noqa: BLE001 - empty category pages are fine
                        log.info("%s: selector %r not found", url, wait_for)
                return page.content()
            except BlockedError:
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt == retries:
                    raise ScrapeError(f"{url}: {exc}") from exc
                log.warning("retrying %s after error: %s", url, exc)
                time.sleep(2 * (attempt + 1))
            finally:
                page.close()
        raise ScrapeError(f"{url}: giving up")


# --------------------------------------------------------------------------- scraper base
class BaseScraper:
    """Subclasses implement `scrape_category` for one of our categories."""

    slug: str = ""
    name: str = ""
    base_url: str = ""
    color: str = "#64748b"
    # our category slug -> list of store-specific locations (URL paths / collection handles)
    categories: dict[str, list[str]] = {}

    def scrape(self, browser: PoliteBrowser, only: list[str] | None = None) -> ScrapeResult:
        result = ScrapeResult()
        seen: set[str] = set()
        for category, locations in self.categories.items():
            if only and category not in only:
                continue
            ok = True
            for location in locations:
                try:
                    items = self.scrape_location(browser, category, location)
                except BlockedError as exc:
                    log.error("[%s] blocked: %s", self.slug, exc)
                    result.errors.append(str(exc))
                    result.blocked = True
                    result.pages_fetched = browser.pages_fetched
                    return result  # stop immediately, never retry around a block
                except ScrapeError as exc:
                    log.error("[%s] %s", self.slug, exc)
                    result.errors.append(str(exc))
                    ok = False
                    continue
                for item in items:
                    if item.store_sku not in seen:  # same product listed in two categories
                        seen.add(item.store_sku)
                        result.items.append(item)
            if ok:
                result.completed_categories.add(category)
            log.info("[%s] %s: %d items so far", self.slug, category, len(result.items))
        result.pages_fetched = browser.pages_fetched
        return result

    def scrape_location(self, browser: PoliteBrowser, category: str, location: str) -> list[ScrapedItem]:
        raise NotImplementedError
