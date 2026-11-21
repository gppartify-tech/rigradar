"""Budget PC build recommender (used by the PC builder page and the chatbot).

The algorithm, in plain words:
1. Split the budget between the categories according to the use case
   (a gaming PC spends ~40% on the graphics card, a workstation spends more on CPU/RAM).
2. Pick parts in dependency order, each time choosing the best performance that fits
   that category's share, while respecting compatibility:
   GPU -> CPU -> motherboard (same socket) -> RAM (same DDR type) -> storage
       -> PSU (enough watts for CPU+GPU) -> case (fits the board) -> cooler (handles the CPU).
3. Balance: if the total is over budget, cheapen the "cosmetic" parts first, then step the
   GPU/CPU down. If money is left, upgrade the part that matters most for the use case.
Only in-stock parts with a known price are used, so every pick can actually be bought.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.constants import CATEGORIES
from app.models import Product
from app.schemas import RecommendIn, RecommendOut
from app.services.compatibility import build_report, estimate_wattage, recommended_psu_watts

ALLOCATIONS: dict[str, dict[str, float]] = {
    "gaming": {"gpu": .40, "cpu": .19, "motherboard": .11, "ram": .08, "storage": .07, "psu": .065, "case": .05, "cooler": .035},
    "streaming": {"gpu": .33, "cpu": .25, "motherboard": .11, "ram": .09, "storage": .07, "psu": .065, "case": .05, "cooler": .035},
    "creator": {"gpu": .27, "cpu": .28, "motherboard": .11, "ram": .12, "storage": .09, "psu": .06, "case": .04, "cooler": .03},
    "workstation": {"gpu": .20, "cpu": .33, "motherboard": .12, "ram": .15, "storage": .09, "psu": .06, "case": .03, "cooler": .02},
    "office": {"cpu": .30, "motherboard": .20, "ram": .15, "storage": .15, "psu": .10, "case": .07, "cooler": .03},
}
# How much a CPU's gaming vs multi-core score matters for each use case.
CPU_WEIGHTS = {"gaming": (.85, .15), "streaming": (.55, .45), "creator": (.3, .7), "workstation": (.1, .9), "office": (.5, .5)}
UPGRADE_ORDER = {
    "gaming": ["gpu", "cpu"], "streaming": ["gpu", "cpu"], "creator": ["cpu", "gpu", "ram"],
    "workstation": ["cpu", "ram", "gpu"], "office": ["cpu", "storage"],
}
USE_CASE_LABEL = {"gaming": "gaming", "streaming": "gaming + streaming", "creator": "content creation",
                  "workstation": "workstation tasks", "office": "office / study"}
# In gaming builds the CPU should not cost more than this share of the graphics card.
CPU_PRICE_VS_GPU = {"gaming": 0.6, "streaming": 0.85}
# A "gaming" PC with a GT 610 is not a gaming PC: below these GPU scores we would rather go over budget.
MIN_GPU_SCORE = {"gaming": 9, "streaming": 9, "creator": 6, "workstation": 6, "office": 0}
# Power supplies are the part where no-name brands are risky (they can take other parts with them).
REPUTABLE_PSU_BRANDS = {
    "Corsair", "Seasonic", "be quiet!", "Cooler Master", "Thermaltake", "MSI", "ASUS", "Gigabyte", "NZXT",
    "Antec", "FSP", "Super Flower", "EVGA", "DeepCool", "Lian Li", "ADATA", "Montech", "Thermalright", "Fractal Design",
    "SilverStone", "Cougar", "XFX", "Phanteks",
}
EFFICIENCY_RANK = {"80+ Titanium": 5, "80+ Platinum": 4, "80+ Gold": 3, "80+ Silver": 2, "80+ Bronze": 1.5, "80+ White": 1}


def _price(p: Product) -> float:
    return float(p.best_price)


def _cheapest(items: list[Product]) -> Product | None:
    return min(items, key=_price) if items else None


def _best_under(items: list[Product], metric: Callable[[Product], float], cap: float) -> Product | None:
    fitting = [p for p in items if _price(p) <= cap]
    if not fitting:
        return None
    return max(fitting, key=lambda p: (metric(p), -_price(p)))


class Recommender:
    def __init__(self, db: Session, req: RecommendIn):
        self.db, self.req = db, req
        self.budget = float(req.budget)
        self.use = req.use_case
        default = [c for c in CATEGORIES if not (c == "gpu" and self.use == "office")]
        self.include = [c for c in CATEGORIES if c in (req.include or default)]
        alloc = dict(ALLOCATIONS[self.use])
        if "gpu" in self.include and "gpu" not in alloc:
            alloc["gpu"] = .25
        if self.use in ("gaming", "streaming") and req.resolution:
            shift = {"1080p": -.04, "1440p": 0, "4k": .06}[req.resolution]
            alloc["gpu"] += shift
            alloc["cpu"] -= shift
        share = sum(alloc[c] for c in self.include) or 1
        self.alloc = {c: alloc[c] / share for c in self.include}
        self.cands = self._load()
        self.picks: dict[str, Product] = {}
        self.notes: list[str] = []

    # -------------------------------------------------------------- data
    def _load(self) -> dict[str, list[Product]]:
        stmt = select(Product).where(
            Product.category.in_(self.include), Product.best_price.is_not(None), Product.offer_count > 0
        ).options(selectinload(Product.best_store))
        if self.req.in_stock_only:
            stmt = stmt.where(Product.in_stock.is_(True))
        out: dict[str, list[Product]] = defaultdict(list)
        for p in self.db.scalars(stmt):
            out[p.category].append(p)
        return out

    def cap(self, category: str) -> float:
        return self.budget * self.alloc.get(category, 0)

    # -------------------------------------------------------------- metrics
    def cpu_metric(self, p: Product) -> float:
        wg, wm = CPU_WEIGHTS[self.use]
        return wg * (p.specs.get("gaming_score") or 40) + wm * (p.specs.get("multi_score") or 20)

    def gpu_metric(self, p: Product) -> float:
        score = p.specs.get("score") or 0
        if self.use in ("creator", "workstation"):
            score += (p.specs.get("vram_gb") or 0) * 0.6  # VRAM matters for 3D / AI work
        return score

    # -------------------------------------------------------------- candidate filters
    def gpus(self) -> list[Product]:
        brand = self.req.gpu_brand
        floor = MIN_GPU_SCORE[self.use]
        return [p for p in self.cands["gpu"] if (p.specs.get("score") or 0) >= floor and p.specs.get("score") is not None
                and (brand == "any" or p.specs.get("chip_maker") == brand)]

    def cpus(self, socket: str | None = None) -> list[Product]:
        brand = self.req.cpu_brand
        needs_igpu = "gpu" not in self.include
        return [p for p in self.cands["cpu"]
                if p.specs.get("socket") and p.specs.get("gaming_score") is not None
                and (brand == "any" or (p.brand or "").lower() == brand)
                and (not needs_igpu or p.specs.get("igpu"))
                and (socket is None or p.specs["socket"] == socket)]

    # -------------------------------------------------------------- pickers
    def pick_motherboard(self, cpu: Product | None, cap: float) -> Product | None:
        boards = self.cands["motherboard"]
        if cpu is not None:
            boards = [b for b in boards if b.specs.get("socket") == cpu.specs.get("socket")]
        if not boards:
            return None
        known = [b for b in boards if b.specs.get("memory_type")]
        boards = known or boards
        big = [b for b in boards if b.specs.get("form_factor") != "Mini-ITX"]
        boards = big or boards
        if cpu is not None and (cpu.specs.get("tdp_w") or 0) >= 150:
            strong = [b for b in boards if b.specs.get("chipset") not in ("A620", "H610", "H810", "A520")]
            boards = strong or boards

        def quality(b: Product) -> float:
            chipset = b.specs.get("chipset") or ""
            tier = {"A": 1, "H": 1, "B": 2, "X": 2.5, "Z": 2.5}.get(chipset[:1], 1.5)
            wifi = 0.5 if b.specs.get("wifi") and self.budget >= 900 else 0
            return tier + wifi

        return _best_under(boards, quality, cap) or _cheapest(boards)

    def ram_target_gb(self) -> int:
        if self.use == "office":
            return 16
        if self.use == "workstation":
            return 64 if self.budget >= 2500 else 32
        if self.use in ("creator", "streaming"):
            return 32
        return 32 if self.budget >= 650 else 16

    def pick_ram(self, board: Product | None, cpu: Product | None, cap: float, target: int) -> Product | None:
        kits = self.cands["ram"]
        mtype = (board.specs.get("memory_type") if board else None)
        if mtype is None and cpu is not None:
            mtype = "DDR4" if cpu.specs.get("socket") in ("AM4", "LGA1200", "LGA1151") else "DDR5"
        kits = [k for k in kits if k.specs.get("memory_type") == mtype] if mtype else kits
        if not kits:
            return None
        preferred_speed = 3200 if mtype == "DDR4" else (6000 if cpu and cpu.specs.get("socket") == "AM5" else 5600)
        for want in sorted({target, 32, 16, 8}, reverse=True):
            if want > target:
                continue
            exact = [k for k in kits if k.specs.get("capacity_gb") == want]
            dual = [k for k in exact if (k.specs.get("modules") or 1) >= 2] or exact
            fast = [k for k in dual if (k.specs.get("speed_mhz") or 0) >= preferred_speed] or dual
            choice = _cheapest(fast)
            if choice and (_price(choice) <= cap * 1.5 or want <= 16):
                return choice
        return _cheapest(kits)

    def storage_target_gb(self) -> int:
        if self.use == "office" or self.budget < 450:
            return 500
        return 2000 if self.budget >= 1500 else 1000

    def pick_storage(self, cap: float, target: int) -> Product | None:
        drives = [d for d in self.cands["storage"] if d.specs.get("storage_type") != "HDD"]
        nvme = [d for d in drives if d.specs.get("storage_type") == "NVMe SSD"] or drives
        for want in (target, 1000, 500):
            fits = [d for d in nvme if (d.specs.get("capacity_gb") or 0) >= want * 0.95]
            if fits:
                choice = _cheapest(fits)
                if _price(choice) <= cap * 1.5 or want <= 500:
                    return choice
        return _cheapest(nvme)

    def pick_psu(self, needed_watts: int) -> Product | None:
        psus = [p for p in self.cands["psu"] if (p.specs.get("wattage") or 0) >= needed_watts
                and p.specs.get("form_factor") != "SFX"]
        if not psus:
            psus = sorted(self.cands["psu"], key=lambda p: -(p.specs.get("wattage") or 0))[:1]
        # reputable brand, and not absurdly oversized (a 1000 W unit for a 400 W PC wastes money)
        sensible = [p for p in psus if p.brand in REPUTABLE_PSU_BRANDS
                    and (p.specs.get("wattage") or 0) <= max(needed_watts + 350, 650)] or psus
        want = 3 if self.budget >= 1200 else (1.5 if self.budget >= 600 else 0)
        good = [p for p in sensible if EFFICIENCY_RANK.get(p.specs.get("efficiency"), 0.5) >= want]
        return _cheapest(good or sensible)

    def pick_case(self, board: Product | None, cap: float) -> Product | None:
        form = board.specs.get("form_factor", "ATX") if board else "ATX"
        cases = [c for c in self.cands["case"] if form in (c.specs.get("supports") or ["ATX", "Micro-ATX", "Mini-ITX"])]
        floor = 25 if self.budget < 1000 else 45
        decent = [c for c in cases if floor <= _price(c) <= max(cap, floor)]
        return _cheapest(decent) or _cheapest(cases)

    def pick_cooler(self, cpu: Product | None) -> Product | None:
        coolers = self.cands["cooler"]
        tdp = (cpu.specs.get("tdp_w") or 100) if cpu else 100
        if tdp > 150:
            fit = [c for c in coolers if (c.specs.get("tdp_rating_w") or 0) >= tdp
                   or (c.specs.get("cooler_type") == "Liquid" and (c.specs.get("radiator_mm") or 0) >= 240)]
        elif tdp > 90:
            fit = [c for c in coolers if (c.specs.get("tdp_rating_w") or 0) >= tdp or _price(c) >= 25]
        else:
            fit = [c for c in coolers if _price(c) >= 10]
        return _cheapest(fit or coolers)

    # -------------------------------------------------------------- build
    def fill_dependents(self) -> None:
        cpu, gpu = self.picks.get("cpu"), self.picks.get("gpu")
        if "motherboard" in self.include:
            self._set("motherboard", self.pick_motherboard(cpu, self.cap("motherboard")))
        board = self.picks.get("motherboard")
        if "ram" in self.include:
            self._set("ram", self.pick_ram(board, cpu, self.cap("ram"), self.ram_target_gb()))
        if "storage" in self.include:
            self._set("storage", self.pick_storage(self.cap("storage"), self.storage_target_gb()))
        if "psu" in self.include:
            core = {k: v for k, v in (("cpu", cpu), ("gpu", gpu)) if v is not None}
            self._set("psu", self.pick_psu(recommended_psu_watts(estimate_wattage(core))))
        if "case" in self.include:
            self._set("case", self.pick_case(board, self.cap("case")))
        if "cooler" in self.include:
            self._set("cooler", self.pick_cooler(cpu))

    def _set(self, category: str, product: Product | None) -> None:
        if product is None:
            self.picks.pop(category, None)
        else:
            self.picks[category] = product

    def total(self) -> float:
        return sum(_price(p) for p in self.picks.values())

    def refresh_psu(self) -> None:
        if "psu" in self.include and "psu" in self.picks:
            need = recommended_psu_watts(estimate_wattage(self.picks))
            if (self.picks["psu"].specs.get("wattage") or 0) < need:
                self._set("psu", self.pick_psu(need))

    def downgrade(self) -> bool:
        """One cheapening step. Returns False when nothing can get cheaper."""
        over = self.total() - self.budget
        cpu = self.picks.get("cpu")
        steps: list[tuple[str, Callable[[], Product | None]]] = [
            ("case", lambda: _cheapest([c for c in self.cands["case"] if self.picks.get("motherboard") is None
                                         or self.picks["motherboard"].specs.get("form_factor", "ATX") in (c.specs.get("supports") or ["ATX"])])),
            ("cooler", lambda: self.pick_cooler(cpu)),  # cheapest cooler that can still handle the CPU
            ("storage", lambda: self.pick_storage(0, 500)),
            ("ram", lambda: self.pick_ram(self.picks.get("motherboard"), cpu, 0, 16)),
            ("motherboard", lambda: _cheapest([b for b in self.cands["motherboard"] if cpu is None
                                                or b.specs.get("socket") == cpu.specs.get("socket")])),
            ("psu", lambda: self.pick_psu(recommended_psu_watts(estimate_wattage(self.picks)))),
        ]
        for category, cheaper in steps:
            current = self.picks.get(category)
            if current is None:
                continue
            alt = cheaper()
            if alt is not None and _price(alt) < _price(current) - 0.5:
                if category == "motherboard":  # a cheaper board may need different RAM
                    self._set(category, alt)
                    self._set("ram", self.pick_ram(alt, cpu, 0, (self.picks.get("ram") or alt).specs.get("capacity_gb") or 16))
                else:
                    self._set(category, alt)
                return True
        # finally step the big parts down - the LESS important one first
        # (for gaming the CPU gives up money before the graphics card does)
        primary = UPGRADE_ORDER[self.use][0]
        for category in sorted(("gpu", "cpu"), key=lambda c: c == primary):
            current = self.picks.get(category)
            if current is None:
                continue
            if category == "gpu":
                pool, metric = self.gpus(), self.gpu_metric
            else:
                pool, metric = self.cpus(socket=current.specs.get("socket")), self.cpu_metric
            pool = [p for p in pool if _price(p) < _price(current)]
            alt = _best_under(pool, metric, _price(current) - over) or _cheapest(pool)
            if alt is not None:
                self._set(category, alt)
                self.refresh_psu()
                return True
        return False

    def upgrade(self) -> bool:
        """One upgrade step with the money left over. Returns False when nothing fits."""
        left = self.budget - self.total()
        if left < max(15, self.budget * 0.02):
            return False
        for category in UPGRADE_ORDER[self.use]:
            current = self.picks.get(category)
            if current is None:
                continue
            if category in ("gpu", "cpu"):
                pool = self.gpus() if category == "gpu" else self.cpus(socket=current.specs.get("socket"))
                metric = self.gpu_metric if category == "gpu" else self.cpu_metric
                better = [p for p in pool if metric(p) > metric(current) * 1.03 and _price(p) <= _price(current) + left]
                if category == "cpu" and self.use in CPU_PRICE_VS_GPU and "gpu" in self.picks:
                    # keep a gaming PC balanced: don't pair a 300 JOD CPU with a 350 JOD graphics card
                    ceiling = max(_price(self.picks["gpu"]) * CPU_PRICE_VS_GPU[self.use], self.cap("cpu"))
                    better = [p for p in better if _price(p) <= ceiling]
                alt = max(better, key=lambda p: (metric(p), -_price(p))) if better else None
            elif category == "ram":
                want = (current.specs.get("capacity_gb") or 16) * 2
                alt = self.pick_ram(self.picks.get("motherboard"), self.picks.get("cpu"), _price(current) + left, want)
                if alt is not None and (alt.specs.get("capacity_gb") or 0) <= (current.specs.get("capacity_gb") or 0):
                    alt = None
            else:  # storage
                want = (current.specs.get("capacity_gb") or 500) * 2
                bigger = [d for d in self.cands["storage"] if d.specs.get("storage_type") == "NVMe SSD"
                          and (d.specs.get("capacity_gb") or 0) >= want and _price(d) <= _price(current) + left]
                alt = _cheapest(bigger)
            if alt is None or alt.id == current.id:
                continue
            backup = dict(self.picks)
            self._set(category, alt)
            self.refresh_psu()
            if self.total() <= self.budget:
                return True
            self.picks = backup  # PSU upgrade pushed us over budget -> undo
        return False

    def run(self) -> RecommendOut:
        if "gpu" in self.include:
            gpus = self.gpus()
            self._set("gpu", _best_under(gpus, self.gpu_metric, self.cap("gpu")) or _cheapest(gpus))
            if not gpus:
                self.notes.append("No suitable graphics card is in stock for these filters right now.")
        if "cpu" in self.include:
            cpus = self.cpus()
            self._set("cpu", _best_under(cpus, self.cpu_metric, self.cap("cpu")) or _cheapest(cpus))
        self.fill_dependents()

        for _ in range(40):
            if self.total() <= self.budget or not self.downgrade():
                break
        for _ in range(12):
            if not self.upgrade():
                break

        report = build_report(self.picks, self._reasons())
        total = report.total_price
        label = USE_CASE_LABEL[self.use]
        split = ", ".join(f"{CATEGORIES[c]['singular']} {round(self.alloc[c] * 100)}%"
                          for c in sorted(self.alloc, key=lambda c: -self.alloc[c])[:3])
        notes = [f"Budget split for {label}: {split} (the rest goes to the supporting parts)."] + self.notes
        if total > self.budget:
            notes.append(f"Even the cheapest compatible in-stock parts cost {total:.0f} JOD, more than your "
                         f"{self.budget:.0f} JOD budget. Consider used parts from the marketplace or a higher budget.")
        elif self.budget - total >= 15:
            notes.append(f"{self.budget - total:.0f} JOD left over - keep it, or put it towards a better "
                         f"{CATEGORIES[UPGRADE_ORDER[self.use][0]]['singular'].lower()} later.")
        missing = [CATEGORIES[c]["singular"] for c in self.include if c not in self.picks]
        if missing:
            notes.append("Couldn't find an in-stock " + ", ".join(missing) + " - check back after the next price update.")
        notes.append("Prices are the lowest in-stock prices from the latest store check; confirm on the store before buying.")
        return RecommendOut(
            **report.model_dump(), budget=self.budget, leftover=round(self.budget - total, 2),
            use_case=self.use, resolution=self.req.resolution, notes=notes,
        )

    def _reasons(self) -> dict[str, str]:
        r: dict[str, str] = {}
        p = self.picks
        if gpu := p.get("gpu"):
            s = gpu.specs
            r["gpu"] = (f"{s.get('chip', 'GPU')} with {s.get('vram_gb', '?')} GB VRAM - the strongest card "
                        f"(performance index {s.get('score', '?')}/100) that fits about {round(self.alloc.get('gpu', 0) * 100)}% of the budget.")
        if cpu := p.get("cpu"):
            s = cpu.specs
            focus = "gaming" if CPU_WEIGHTS[self.use][0] >= .5 else "multi-core"
            r["cpu"] = f"{s.get('cores', '?')} cores / {s.get('threads', '?')} threads, strong {focus} performance for the price ({s.get('socket')})."
        if mb := p.get("motherboard"):
            s = mb.specs
            r["motherboard"] = (f"{s.get('chipset', '')} board for socket {s.get('socket')}, {s.get('memory_type', '?')}, "
                                f"{s.get('form_factor', 'ATX')}{', Wi-Fi' if s.get('wifi') else ''}.")
        if ram := p.get("ram"):
            s = ram.specs
            r["ram"] = (f"{s.get('capacity_gb')} GB {s.get('memory_type', '')}"
                        f"{'-' + str(s['speed_mhz']) if s.get('speed_mhz') else ''}"
                        f"{' dual-channel kit' if (s.get('modules') or 1) >= 2 else ''} - matches the motherboard.")
        if st := p.get("storage"):
            s = st.specs
            cap = s.get("capacity_gb") or 0
            r["storage"] = f"{cap // 1000 if cap >= 1000 else cap}{'TB' if cap >= 1000 else 'GB'} {s.get('storage_type', 'SSD')} for fast boot and load times."
        if psu := p.get("psu"):
            s = psu.specs
            r["psu"] = (f"{s.get('wattage')} W {s.get('efficiency', '')} - covers the estimated "
                        f"{estimate_wattage(p)} W load with headroom.").replace("  ", " ")
        if case := p.get("case"):
            r["case"] = f"{case.specs.get('form_factor', 'Tower')} case that fits the motherboard."
        if cooler := p.get("cooler"):
            tdp = p["cpu"].specs.get("tdp_w") if p.get("cpu") else None
            r["cooler"] = f"{cooler.specs.get('cooler_type', 'Air')} cooler{f' for a ~{tdp} W CPU' if tdp else ''}."
        return r


def recommend(db: Session, req: RecommendIn) -> RecommendOut:
    return Recommender(db, req).run()
