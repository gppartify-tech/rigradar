# Choosing and scraping the stores

This document explains which stores Partify scrapes, why, and how – useful for the
"methodology" chapter of the graduation report. All findings were checked live on
**20 November 2026**.

## 1. Selection criteria

1. **Popular** – a store people in Jordan actually buy PC parts from, with a large component catalog.
2. **Easy to scrape** – stable, server-rendered pages or a structured feed; no CAPTCHAs or bot challenges.
3. **Allowed** – the store's `robots.txt` permits the pages we need. We do not try to get around
   any protection: a bot challenge means "no".
4. **Comparable** – same country and currency (JOD), so prices can be compared directly.

## 2. Candidates and results

| Candidate | Result | Reason |
|---|---|---|
| Newegg (US) | ✗ rejected | Cloudflare "Just a moment…" challenge on every page |
| Micro Center (US) | ✗ rejected | Cloudflare challenge (even on robots.txt) |
| eBay (US) | ✗ rejected | robots.txt: `Disallow: /sch/` (search results) for all crawlers |
| City Center – citycenter.jo | ✗ rejected | Very popular, but robots.txt disallows search (`/search`, `?search=`), pagination (`/*?page=`), sorting and `limit` for bots – only the first 16 products of each category are reachable without a 6 MB sitemap and one request per product |
| XMART – xmart.jo | ✗ rejected | Shopify (easy), but mostly appliances – few PC components |
| **iGeek Megastore – igeekjo.com** | ✓ chosen | Shopify, ~950 PC components, JSON feed allowed |
| **CompuJordan – compujordan.com** | ✓ chosen | OpenCart, robots.txt allows everything except `/admin/` |
| **Oriental Store – os-jo.com** | ✓ chosen | OpenCart, clean product cards, category pagination allowed |

## 3. How each store is scraped

### iGeek Megastore (Shopify) – structured JSON
Shopify exposes each collection as JSON: `https://igeekjo.com/collections/pcb-gpu/products.json?limit=250&page=1`.
Each product has `title`, `vendor` (brand), `handle` (URL), `variants[].price`, `variants[].available`
and `images`. The store currency (`/meta.json`) is JOD. iGeek's `pcb-*` collections are its own PC-builder
categories, so they map 1:1 to ours. Edge cases handled: price `0.000` means "showroom only / call for
price" (treated as no price), and some products have a `compare_at_price` *lower* than the price
(ignored). One run: **13 requests, ~40 s, 637 products**.

### CompuJordan (OpenCart) – rendered HTML, 100 per page
`https://compujordan.com/computer-hardware/components/graphic-card?limit=100&page=1`, rendered with
Playwright. Product cards: `.product-thumb` → name/link in `h4 a`, price in `p.price`
(`.price-regular`, or `.price-old` + `.price-new` during a sale). An out-of-stock card shows
`.tb_label_stock_status` ("Out Of Stock") instead of the *Add to cart* button; the store id comes
from `cart.add('3162', …)`. Product links carry `?limit=100`, which is stripped.
One run: **9 requests, ~30 s, 494 products** (most GPUs were out of stock on the test day).

### Oriental Store (OpenCart, custom theme) – rendered HTML + pagination
`https://os-jo.com/graphics-cards`, then the URL in `<link rel="next">` (`?page=2`, …).
Cards are `article.card` with `.card-brand`, `.card-name a` (full name in `title`), a short spec line
`.card-line` ("RTX 5080 · 16GB GDDR7"), `.card-price .price` (`<small>JOD</small>2199`), `s.was`
(old price) and `.stock`. The store id is on the add-to-cart button (`data-add`). Oriental keeps old
products listed (out of stock), so categories are long: **91 requests, ~4.5 min, 2,130 products**.
Its robots.txt carries Cloudflare *content signals* `search=yes, ai-train=no` – a price-comparison
index is "search"; the data is never used to train AI models.

## 4. Scraping etiquette (enforced in code – `app/scraping/base.py`)

| Rule | How |
|---|---|
| Follow robots.txt | `robots.py` implements RFC 9309 (wildcards `*`, `$`, longest match wins); every URL is checked before it is requested |
| Be gentle | ≥ 2.5 s (+ random jitter) between requests to the same store; one store at a time; one full scrape every 6 hours |
| Download only what we need | images, fonts, stylesheets, media and any third-party request (analytics, ads) are aborted in the browser |
| Identify ourselves | user agent contains `PartifyBot/1.0; academic price-comparison project` |
| Never bypass protection | HTTP 403/429 or a "Just a moment" challenge page stops the store's scrape immediately |
| Fail safely | network errors are retried twice with back-off; a crashed or blocked run is recorded on the admin page |

## 5. Matching the same product across stores

The stores name the same card differently:

```
iGeek     ASUS PRIME GeForce RTX 5060 8GB GDDR7 OC Edition Graphics Card – DLSS 4, Triple Fans
Oriental  ASUS PRIME GeForce RTX 5060 OC Edition 8GB GDDR7 - Graphics Card
```

`normalize.parse_part()` reduces each title to:

| Part | Example | Must be… |
|---|---|---|
| key | `gpu\|asus\|rtx 5060\|8` (category, brand, chip, VRAM) | equal |
| flags | colour editions (`white`, Gigabyte `ice`), GPU `MAX`/`SFF`, board `wifi`/`ddr4`, PSU `sfx` | equal |
| codes | tokens with digits that name a model: `b650m`, `rm850e`, `kc3000`, `3` in "Lancool 3" | equal |
| words | remaining model words: `prime oc` | fuzzy similar (RapidFuzz ≥ 85–90) |

A bare subset of generic words never matches a named line ("OC" alone ≠ "WINDFORCE OC"). CPUs only
need the model number (`ryzen 7 7800x3d`); boxed and tray versions are the same product.
Specs (socket, cores, VRAM, DDR type, capacity, wattage, radiator size…) are extracted with regular
expressions and enriched from `app/data/specs_db.py` (CPU/GPU reference table).

Result on the test day: **3,015 store listings → 2,387 products**, of which **706 in stock**,
**295 sold by 2+ stores** and **31 by all three**. Most products are unique to one store – the stores
carry different board-partner models – but CPUs, SSDs and popular GPUs overlap a lot.

When the rules improve, `python -m app.cli rematch` rebuilds the products from the stored listings
without contacting the stores again.

## 6. When a store changes its website
1. The admin page shows the run as `failed` / `partial` (0 items, or an HTTP error).
2. Save the new page (`curl` or the browser) into `backend/tests/fixtures/`.
3. Fix the store's `parse_*` function until its test passes, then run the scraper.
