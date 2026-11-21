"""Build compatibility checks (the PC-builder rules).

Every rule returns a human readable issue:
  error   - the parts physically/electrically do not work together
  warning - it works, but there is a real downside
  info    - a reminder worth checking
"""
from __future__ import annotations

import math

from app.constants import CATEGORIES
from app.models import Product
from app.schemas import BuildCheckOut, BuildPartOut, CompatIssue, ProductSummaryOut

BASE_SYSTEM_WATTS = 60  # motherboard, RAM, SSD, fans, USB devices
ENTRY_CHIPSETS = {"A620", "H610", "H810", "A520"}


def estimate_wattage(parts: dict[str, Product]) -> int:
    watts = BASE_SYSTEM_WATTS
    if cpu := parts.get("cpu"):
        watts += int(cpu.specs.get("tdp_w") or 125)
    if gpu := parts.get("gpu"):
        watts += int(gpu.specs.get("tdp_w") or 200)
    return watts


def recommended_psu_watts(watts: int) -> int:
    """40% headroom for power spikes and PSU efficiency, rounded up to 50 W (min 450 W)."""
    return max(450, math.ceil(watts * 1.4 / 50) * 50)


def check_parts(parts: dict[str, Product]) -> list[CompatIssue]:
    issues: list[CompatIssue] = []

    def add(level: str, message: str) -> None:
        issues.append(CompatIssue(level=level, message=message))

    cpu, mb, ram, gpu = parts.get("cpu"), parts.get("motherboard"), parts.get("ram"), parts.get("gpu")
    psu, case, cooler = parts.get("psu"), parts.get("case"), parts.get("cooler")
    s = {k: (p.specs or {}) for k, p in parts.items()}

    # CPU <-> motherboard socket
    if cpu and mb:
        cs, ms = s["cpu"].get("socket"), s["motherboard"].get("socket")
        if cs and ms and cs != ms:
            add("error", f"The CPU uses socket {cs} but the motherboard is {ms} - they don't fit together.")
        chipset = s["motherboard"].get("chipset")
        if chipset in ENTRY_CHIPSETS and (s["cpu"].get("tdp_w") or 0) >= 150:
            add("warning", f"{chipset} is an entry-level chipset; a {s['cpu'].get('tdp_w')} W CPU may throttle on its power delivery.")
        model = s["cpu"].get("model", "")
        if model.endswith(("K", "KF")) and chipset and not chipset.startswith("Z"):
            add("info", f"An unlocked Intel 'K' CPU can only be overclocked on a Z-series board (this one is {chipset}).")

    # Motherboard <-> RAM
    if mb and ram:
        mt, rt = s["motherboard"].get("memory_type"), s["ram"].get("memory_type")
        if mt and rt and mt != rt:
            add("error", f"The motherboard takes {mt} memory but the RAM kit is {rt}.")
        elif rt and not mt:
            add("warning", f"Check that the motherboard supports {rt} - some boards for this socket exist in DDR4 and DDR5 versions.")
        if s["motherboard"].get("form_factor") == "Mini-ITX" and (s["ram"].get("modules") or 1) > 2:
            add("error", "Mini-ITX boards have only 2 memory slots but this kit has more modules.")
    if ram and (s["ram"].get("modules") or 2) == 1:
        add("info", "A single memory stick runs in single-channel mode; a 2-stick kit is noticeably faster.")

    # Case <-> motherboard size
    if case and mb:
        form = s["motherboard"].get("form_factor", "ATX")
        supports = s["case"].get("supports") or ["ATX", "Micro-ATX", "Mini-ITX"]
        if form not in supports:
            add("error", f"A {form} motherboard does not fit in this {s['case'].get('form_factor', '')} case.")

    # Power
    watts = estimate_wattage(parts)
    if psu:
        capacity = s["psu"].get("wattage")
        if capacity:
            if capacity < watts:
                add("error", f"The PSU ({capacity} W) is weaker than the estimated load ({watts} W).")
            elif capacity < recommended_psu_watts(watts):
                add("warning", f"The PSU ({capacity} W) has little headroom; {recommended_psu_watts(watts)} W is recommended.")

    # Graphics output
    if cpu and not gpu and s["cpu"].get("igpu") is False:
        add("error", "This CPU has no integrated graphics, so the build needs a graphics card for a display.")

    # Cooling
    if cpu and cooler:
        rating, tdp = s["cooler"].get("tdp_rating_w"), s["cpu"].get("tdp_w") or 0
        if rating and tdp > rating:
            add("warning", f"The cooler is rated for {rating} W but the CPU can draw ~{tdp} W.")
        if s["cooler"].get("cooler_type") == "Liquid" and case:
            add("info", f"Make sure the case has room for a {s['cooler'].get('radiator_mm', '')} mm radiator.")
    elif cpu and not cooler and (s["cpu"].get("packaging") == "Tray" or (s["cpu"].get("tdp_w") or 0) >= 120):
        add("info", "Add a CPU cooler - tray and high-power CPUs don't come with one.")

    if gpu and case:
        add("info", "Check the graphics card length against the case's maximum GPU length.")

    missing = [CATEGORIES[c]["singular"] for c in ("cpu", "motherboard", "ram", "storage", "psu", "case") if c not in parts]
    if missing and len(parts) > 1:
        add("info", "Still missing: " + ", ".join(missing) + ".")
    return issues


def build_report(parts: dict[str, Product], reasons: dict[str, str] | None = None) -> BuildCheckOut:
    ordered = [c for c in CATEGORIES if c in parts]
    part_out = [
        BuildPartOut(
            category=c,
            product=ProductSummaryOut.model_validate(parts[c]),
            price=float(parts[c].best_price) if parts[c].best_price is not None else None,
            reason=(reasons or {}).get(c),
        )
        for c in ordered
    ]
    issues = check_parts(parts)
    watts = estimate_wattage(parts)
    return BuildCheckOut(
        parts=part_out,
        total_price=round(sum(p.price or 0 for p in part_out), 2),
        estimated_wattage=watts,
        recommended_psu_w=recommended_psu_watts(watts),
        issues=issues,
        compatible=not any(i.level == "error" for i in issues),
    )
