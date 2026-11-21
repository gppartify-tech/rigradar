"""Fixed vocabularies shared by the API, scrapers and frontend."""

# The part categories we track. Order = order shown in the UI and in a build.
CATEGORIES: dict[str, dict[str, str]] = {
    "cpu": {"name": "Processors", "singular": "CPU"},
    "gpu": {"name": "Graphics Cards", "singular": "Graphics card"},
    "motherboard": {"name": "Motherboards", "singular": "Motherboard"},
    "ram": {"name": "Memory (RAM)", "singular": "Memory kit"},
    "storage": {"name": "Storage", "singular": "Storage drive"},
    "psu": {"name": "Power Supplies", "singular": "Power supply"},
    "case": {"name": "Cases", "singular": "Case"},
    "cooler": {"name": "CPU Coolers", "singular": "CPU cooler"},
}
CATEGORY_SLUGS = tuple(CATEGORIES)

# Marketplace item condition.
CONDITIONS: dict[str, str] = {
    "new": "New (sealed)",
    "like_new": "Like new",
    "good": "Used - good",
    "fair": "Used - fair",
    "for_parts": "For parts / not working",
}

LISTING_STATUSES = ("active", "sold", "hidden")

JORDAN_CITIES = (
    "Amman", "Zarqa", "Irbid", "Aqaba", "Salt", "Madaba", "Jerash",
    "Mafraq", "Karak", "Ajloun", "Ma'an", "Tafilah",
)

# Marketplace listings may also be for whole PCs / laptops / peripherals.
LISTING_CATEGORIES: dict[str, str] = {
    **{slug: meta["name"] for slug, meta in CATEGORIES.items()},
    "pc": "Complete PCs",
    "laptop": "Laptops",
    "monitor": "Monitors",
    "peripheral": "Peripherals",
    "other": "Other",
}

NOTIFICATION_KINDS = ("target_reached", "price_drop", "back_in_stock", "system")
