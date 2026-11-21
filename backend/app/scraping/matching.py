"""Cross-store product matching (a small "entity resolution" problem).

Given a freshly parsed listing, find the canonical Product it belongs to, or create one.

Two listings are the same product when ALL of these hold:
1. same category and same match key   (e.g. "gpu|asus|rtx 5070 ti|16")
2. same variant flags                 (WiFi / white / "MAX" / DDR4 ...)
3. same model codes                   (e.g. {"b650m"} or {"rm850e"})
4. similar model words                (fuzzy score >= threshold, see below)

We deliberately prefer *missing* a match over a wrong one: two separate product
pages are a small annoyance, but comparing the prices of two different cards
would mislead users.
"""
from __future__ import annotations

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.scraping.normalize import ParsedPart

# Minimum fuzzy similarity of the model words, per category.
THRESHOLDS = {
    "cpu": 0,  # the CPU model number alone identifies the part
    "gpu": 85,
    "motherboard": 90,
    "ram": 85,
    "storage": 85,
    "psu": 85,
    "case": 87,
    "cooler": 87,
}
# Words too generic to identify a product line on their own: "OC" must not match "WINDFORCE OC".
GENERIC_WORDS = {"oc", "gaming", "rgb", "argb", "edition", "pro", "plus", "v2", "x", "a", "e"}


def words_match(a: str, b: str, threshold: int) -> tuple[bool, float]:
    set_a, set_b = set(a.split()), set(b.split())
    if not set_a and not set_b:
        return True, 100.0
    if not set_a or not set_b:
        return False, 0.0
    score = fuzz.token_set_ratio(a, b)
    if set_a != set_b and (set_a < set_b or set_b < set_a):
        smaller = set_a if set_a < set_b else set_b
        if not smaller - GENERIC_WORDS:
            return False, score
    return score >= threshold, score


def is_same_part(parsed: ParsedPart, product: Product) -> tuple[bool, float]:
    if product.category != parsed.category or product.match_key != parsed.key:
        return False, 0.0
    if parsed.category == "cpu":
        return True, 100.0
    specs = product.specs or {}
    if set(specs.get("_flags", [])) != set(parsed.flags):
        return False, 0.0
    if set(specs.get("_codes", [])) != set(parsed.codes):
        return False, 0.0
    return words_match(parsed.words, specs.get("_words", ""), THRESHOLDS.get(parsed.category, 87))


def find_match(db: Session, parsed: ParsedPart, min_id: int = 0) -> Product | None:
    candidates = db.scalars(
        select(Product).where(
            Product.category == parsed.category, Product.match_key == parsed.key, Product.id > min_id
        )
    ).all()
    best, best_score = None, -1.0
    for product in candidates:
        same, score = is_same_part(parsed, product)
        if same and score > best_score:
            best, best_score = product, score
    return best


def find_or_create_product(
    db: Session, parsed: ParsedPart, image_url: str | None, min_id: int = 0
) -> tuple[Product, bool]:
    product = find_match(db, parsed, min_id)
    if product is not None:
        # Fill in specs the existing product does not know yet (e.g. VRAM from a better title).
        merged = dict(product.specs or {})
        changed = False
        for key, value in parsed.specs.items():
            if key not in merged and value is not None:
                merged[key] = value
                changed = True
        if changed:
            product.specs = merged
        if not product.image_url and image_url:
            product.image_url = image_url
        return product, False

    product = Product(
        category=parsed.category,
        brand=parsed.brand,
        name=parsed.name,
        match_key=parsed.key,
        specs=parsed.specs_with_internals(),
        image_url=image_url,
    )
    db.add(product)
    db.flush()  # assigns product.id
    return product, True
