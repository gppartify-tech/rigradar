"""Understand store product titles.

Each store names the same part differently, e.g.
    iGeek       "AMD Ryzen 7 7800X3D Processor – 8 Cores, 96MB Cache, Up to 5.0GHz, AM5, Tray"
    CompuJordan "AMD Ryzen 7 7800X3D Desktop Processor"
    Oriental    "AMD RYZEN 7 7800X3D Up to 5.0GHz 8 Cores 16 threads 96MB Cache AM5 CPU"

`parse_part()` turns a title into a ParsedPart with:
* specs  - structured facts (socket, VRAM, capacity, wattage...) for filters,
           the compatibility checker and the recommender;
* key    - a coarse identity ("gpu|ASUS|rtx 5070 ti|16") - two listings can only be the
           same product if their keys are equal;
* codes  - model codes (tokens with digits, e.g. "b650m", "rm850e") that must also be equal;
* words  - the remaining model words ("tuf oc") compared with fuzzy matching.

It returns None for items that are not really parts of that category
(case fans in the cooler section, laptop RAM, USB drives...).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.data.specs_db import CHIPSET_SOCKET, CPUS, DDR4_ONLY_SOCKETS, DDR5_ONLY_SOCKETS, GPUS

# --------------------------------------------------------------------------- brands
_BRANDS: list[tuple[str, str]] = [
    ("AMD", r"amd"), ("Intel", r"intel"), ("NVIDIA", r"nvidia"),
    ("ASUS", r"asus|rog|tuf"), ("MSI", r"msi"), ("Gigabyte", r"gigabyte|aorus"),
    ("ASRock", r"asrock"), ("Zotac", r"zotac"), ("PNY", r"pny"), ("Palit", r"palit"),
    ("Inno3D", r"inno\s?3d"), ("Gainward", r"gainward"), ("Galax", r"galax"),
    ("Sapphire", r"sapphire"), ("PowerColor", r"power\s?color"), ("XFX", r"xfx"),
    ("Biostar", r"biostar"), ("Colorful", r"colorful"), ("Arktek", r"arktek"),
    ("Yeston", r"yeston"), ("Maxsun", r"maxsun"), ("Afox", r"afox"), ("Sparkle", r"sparkle"),
    ("Corsair", r"corsair"), ("G.Skill", r"g\.?\s?skill"), ("Kingston", r"kingston|hyperx"),
    ("Crucial", r"crucial"), ("TeamGroup", r"team\s?group|t-?force"), ("ADATA", r"adata|xpg"),
    ("Patriot", r"patriot"), ("Lexar", r"lexar"), ("Netac", r"netac"), ("Klevv", r"klevv"),
    ("GeIL", r"geil"), ("Silicon Power", r"silicon\s?power"), ("Samsung", r"samsung"),
    ("WD", r"western\s+digital|wd_?black|wd"), ("Seagate", r"seagate"), ("SanDisk", r"sandisk"),
    ("Toshiba", r"toshiba"), ("Kioxia", r"kioxia"), ("Hikvision", r"hikvision"),
    ("Hiksemi", r"hiksemi"), ("Transcend", r"transcend"), ("Sabrent", r"sabrent"),
    ("Solidigm", r"solidigm"), ("Micron", r"micron"), ("Apacer", r"apacer"), ("Dahua", r"dahua"),
    ("SK hynix", r"sk\s?hynix|hynix"), ("Seasonic", r"sea\s?sonic"), ("EVGA", r"evga"),
    ("Antec", r"antec"), ("FSP", r"fsp"), ("Super Flower", r"super\s?flower"),
    ("Thermaltake", r"thermaltake"), ("be quiet!", r"be\s?quiet!?"),
    ("Cooler Master", r"cooler\s?master"), ("NZXT", r"nzxt"), ("Lian Li", r"lian[\s-]?li"),
    ("DeepCool", r"deep\s?cool"), ("Montech", r"montech"), ("Gamdias", r"gamdias"),
    ("Xigmatek", r"xigmatek"), ("Aerocool", r"aerocool"), ("Cougar", r"cougar"),
    ("1stPlayer", r"1st\s?player"), ("Phanteks", r"phanteks"), ("Fractal Design", r"fractal(?:\s+design)?"),
    ("Hyte", r"hyte"), ("Jonsbo", r"jonsbo"), ("InWin", r"in\s?win"), ("SilverStone", r"silver\s?stone"),
    ("Darkflash", r"dark\s?flash"), ("Zalman", r"zalman"), ("Sharkoon", r"sharkoon"),
    ("GameMax", r"game\s?max"), ("Fantech", r"fantech"), ("Redragon", r"redragon"),
    ("Havit", r"havit"), ("Segotep", r"segotep"), ("Noctua", r"noctua"), ("Arctic", r"arctic"),
    ("Thermalright", r"thermal\s?right"), ("ID-Cooling", r"id[\s-]?cooling"),
    ("Scythe", r"scythe"), ("Alseye", r"alseye"), ("EK", r"ekwb|ek"), ("Valkyrie", r"valkyrie"),
    ("Razer", r"razer"), ("Asus", r"asus"),
]
_BRAND_RES = [(name, re.compile(rf"(?<![a-z0-9])(?:{pat})(?![a-z0-9])", re.I)) for name, pat in _BRANDS]
_CHIP_MAKERS = {"AMD", "Intel", "NVIDIA"}


def detect_brand(text: str, category: str | None = None) -> str | None:
    """Earliest brand mentioned in the text (AMD/Intel/NVIDIA only count for CPUs/GPUs
    or when nothing else matches, because coolers say "for Intel/AMD")."""
    found: list[tuple[int, int, str]] = []
    for name, regex in _BRAND_RES:
        if m := regex.search(text):
            found.append((m.start(), -len(m.group(0)), name))
    if not found:
        return None
    found.sort()
    if category not in ("cpu", "gpu", "motherboard"):
        non_chip = [f for f in found if f[2] not in _CHIP_MAKERS]
        if non_chip:
            return non_chip[0][2]
    return found[0][2]


def normalize_brand(hint: str | None) -> str | None:
    if not hint:
        return None
    return detect_brand(hint, "cpu")


# --------------------------------------------------------------------------- text helpers
_DASHES = str.maketrans({"–": "-", "—": "-", "‒": "-", "™": "", "®": "", " ": " ", "×": "x"})
_TAIL_SPLIT = re.compile(r"\s+[-|]\s+|,\s|\s\(|\s/\s|\s\[")
_GENERIC_SUFFIX = re.compile(
    r"\s*\b(?:gaming\s+)?(?:graphics?\s+card|video\s+card|desktop\s+processor|cpu\s+processor|processor|"
    r"desktop\s+memory|memory\s+kit|motherboard|power\s+supply|pc\s+case|computer\s+case|"
    r"cpu\s+cooler|solid\s+state\s+drive)\s*$",
    re.I,
)


def tidy(title: str) -> str:
    return re.sub(r"\s+", " ", title.translate(_DASHES)).strip()


def display_name(title: str) -> str:
    """The product name without the marketing tail ('- 8 Cores, 16 Threads ...')."""
    text = tidy(title)
    head = _TAIL_SPLIT.split(text, maxsplit=1)[0].strip(" -,")
    if len(head.split()) < 2:
        head = text
    head = _GENERIC_SUFFIX.sub("", head).strip(" -,")
    return head or text


_STOPWORDS = set(
    """graphics graphic card video gpu cpu processor processors desktop unlocked boxed box tray
    edition motherboard mainboard memory ram kit internal solid state drive ssd hdd nvme m2
    power supply psu case chassis tower mid full mini cooler cooling air liquid aio radiator
    with and for the w new original series generation socket pcie pci express support supports
    geforce radeon nvidia amd intel core ultra ryzen black gb tb channel triple inch
    up to sequential read write speed speeds fast cache cores threads boost clock base
    architecture technology warranty year years compatible ready design lighting
    module modules desktop pc computer fan fans cooler heatsink heat sink sink version model
    gen black edition high performance""".split()
)
_SPEC_TOKEN = re.compile(
    r"""^(?:
        \d+(?:gb|tb|mb|g|t|mhz|ghz|mt|mts|w|mm|hz|bit|rpm|cm|v|a|nm|x|p|k|ms)
      | cl\d+ | c\d\d | ddr\d | gddr\d\w? | d[45] | lpddr\d\w?
      | gen\d | pcie\d* | \d+x\d+\w* | x\d+ | [op]\d{1,2}g
      | 80\+? | atx\d* | usb\d* | wifi\d*e? | ax\d+ | be\d+ | \d+(?:st|nd|rd|th)
      | 2280 | 2242 | 2230 | 12vhpwr | 12v | 24pin | 8pin | rgb\d* | argb\d* | \d+inch | \d+in1 | sata\d
    )$""",
    re.X,
)


_ROMAN = {"ii": "2", "iii": "3", "iv": "4"}


def tokens(text: str) -> list[str]:
    t = tidy(text).lower()
    t = t.replace("wi-fi", "wifi").replace("m.2", "m2").replace("w/", " ")
    t = re.sub(r"\d+\.\d+", " ", t)  # version numbers / sizes: PCIe 4.0, ATX 3.1, 2.5"
    # "Gen 4", "SATA 3", "WiFi 7" -> one spec token, so the lone digit is not taken as a model code
    t = re.sub(r"\b(gen|sata|pcie|usb|ddr|gddr|atx|wifi)\s+(\d)\b", r"\1\2", t)
    return [_ROMAN.get(tok, tok) for tok in re.split(r"[^a-z0-9+]+", t) if tok]


def _brand_tokens(brand: str | None) -> set[str]:
    out = {"asus", "rog", "aorus"} if brand in ("ASUS", "Gigabyte") else set()
    if brand:
        out |= {tok for tok in tokens(brand)}
    return out


@dataclass
class ParsedPart:
    category: str
    brand: str | None
    name: str
    key: str
    words: str
    codes: frozenset[str]
    flags: frozenset[str]
    specs: dict = field(default_factory=dict)

    def specs_with_internals(self) -> dict:
        return {
            **self.specs,
            "_words": self.words,
            "_codes": sorted(self.codes),
            "_flags": sorted(self.flags),
        }


# --------------------------------------------------------------------------- CPU
_AMD_CPU = re.compile(r"\bryzen\s*(3|5|7|9)\s*(?:pro\s*)?(\d{4})\s*(x3d2|x3d|xt|x|gt|ge|g|f)?(?![a-z0-9])", re.I)
_ATHLON = re.compile(r"\bathlon\s*(?:gold\s*|silver\s*)?(\d{3,4})\s*(ge|g)?(?![a-z0-9])", re.I)
_INTEL_CORE = re.compile(r"\b(?:core\s*)?i([3579])\s*-?\s*(\d{4,5})([a-z]{0,2})(?![a-z0-9])", re.I)
_INTEL_ULTRA = re.compile(r"\b(?:core\s*)?ultra\s*([3579])\s*(\d{3})([a-z]{0,2})(?![a-z0-9])(\s*plus\b)?", re.I)


def cpu_model(title: str) -> tuple[str, str] | None:
    """-> ("AMD", "ryzen 7 7800x3d") / ("Intel", "core i5-14400f") / ("Intel", "core ultra 7 265k")"""
    if m := _AMD_CPU.search(title):
        return "AMD", f"ryzen {m.group(1)} {m.group(2)}{(m.group(3) or '').lower()}"
    if m := _ATHLON.search(title):
        return "AMD", f"athlon {m.group(1)}{(m.group(2) or '').lower()}"
    if m := _INTEL_ULTRA.search(title):
        plus = " plus" if m.group(4) else ""
        return "Intel", f"core ultra {m.group(1)} {m.group(2)}{m.group(3).lower()}{plus}"
    if m := _INTEL_CORE.search(title):
        return "Intel", f"core i{m.group(1)}-{m.group(2)}{m.group(3).lower()}"
    return None


def pretty_cpu(model: str) -> str:
    parts = []
    for word in model.split(" "):
        if word in ("ryzen", "core", "ultra", "plus", "athlon"):
            parts.append(word.capitalize())
        elif word.startswith("i") and "-" in word:
            tier, num = word.split("-", 1)
            parts.append(f"{tier}-{num.upper()}")
        else:
            parts.append(word.upper())
    return " ".join(parts)


def _infer_cpu(model: str) -> dict:
    """Fallback for CPUs missing from the reference table."""
    spec: dict = {}
    if model.startswith("athlon"):
        return {"socket": "AM4", "igpu": True, "gaming_score": 25, "multi_score": 6}
    if model.startswith("ryzen"):
        num = re.search(r"(\d{4})", model).group(1)
        spec["socket"] = "AM5" if int(num[0]) >= 7 else "AM4"
        spec["igpu"] = model.endswith("g") or (spec["socket"] == "AM5" and not model.endswith("f"))
    elif "ultra" in model:
        spec["socket"] = "LGA1851"
        spec["igpu"] = "f" not in model.split()[3]
    else:
        num = re.search(r"-(\d{4,5})", model).group(1)
        gen = int(num[:2]) if len(num) == 5 else int(num[0])
        spec["socket"] = {10: "LGA1200", 11: "LGA1200"}.get(gen, "LGA1700" if gen >= 12 else "LGA1151")
        spec["igpu"] = not re.search(r"\d(k?f)$", model)
    return spec


def _parse_cpu(title: str, specs: dict) -> tuple[str, str] | None:
    found = cpu_model(title)
    if not found:
        return None
    maker, model = found
    specs["model"] = pretty_cpu(model)
    if ref := CPUS.get(model):
        cores, threads, boost, power, socket, igpu, gaming, multi = ref
        specs.update(cores=cores, threads=threads, boost_ghz=boost, tdp_w=power, socket=socket,
                     igpu=igpu, gaming_score=gaming, multi_score=multi)
    else:
        specs.update(_infer_cpu(model))
        specs["tdp_w"] = 125
    low = title.lower()
    if "tray" in low:
        specs["packaging"] = "Tray"
    elif re.search(r"\bbox(ed)?\b", low):
        specs["packaging"] = "Box"
    return maker, model


# --------------------------------------------------------------------------- GPU
_NV_GPU = re.compile(r"(?<![a-z0-9])(rtx|gtx|gt)\s*-?\s*(\d{3,4})\s*(ti\s*super|ti|super)?(?![a-z0-9])", re.I)
_AMD_GPU = re.compile(r"(?<![a-z0-9])rx\s*-?\s*(\d{3,4})\s*(xtx|xt|gre)?(?![a-z0-9])", re.I)
_BARE_GEFORCE = re.compile(r"geforce\s*(\d{3,4})\s*(ti\s*super|ti|super)?(?![a-z0-9])", re.I)
_ARC_GPU = re.compile(r"(?<![a-z0-9])arc\s*-?\s*([ab]\d{3})(?![a-z0-9])", re.I)
_VRAM = re.compile(r"(?<![a-z0-9])(\d{1,2})\s*gb?(?![a-z0-9])", re.I)
_VALID_VRAM = {2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32}


def gpu_chip(title: str) -> tuple[str, re.Match] | None:
    if m := _NV_GPU.search(title):
        suffix = re.sub(r"\s+", " ", (m.group(3) or "").lower()).strip()
        return f"{m.group(1).lower()} {m.group(2)}{' ' + suffix if suffix else ''}", m
    if m := _AMD_GPU.search(title):
        return f"rx {m.group(1)}{' ' + m.group(2).lower() if m.group(2) else ''}", m
    if m := _ARC_GPU.search(title):
        return f"arc {m.group(1).lower()}", m
    if m := _BARE_GEFORCE.search(title):  # "MSI GeForce 1650 Super" (no GTX/RTX prefix)
        num = m.group(1)
        family = "gt" if len(num) == 3 else ("gtx" if num.startswith("1") else "rtx")
        suffix = re.sub(r"\s+", " ", (m.group(2) or "").lower()).strip()
        return f"{family} {num}{' ' + suffix if suffix else ''}", m
    return None


def pretty_chip(chip: str) -> str:
    out = []
    for w in chip.split():
        out.append({"ti": "Ti", "super": "Super", "arc": "Arc", "gre": "GRE"}.get(w, w.upper()))
    return " ".join(out)


# Words that turn a GPU into a different SKU of the same line ("EAGLE OC" vs "EAGLE MAX OC").
_GPU_MODIFIERS = re.compile(r"\b(max|sff|low\s?profile|lp|mini|itx|dhahab|limited)\b")


def _parse_gpu(title: str, specs: dict) -> tuple[str, int | None, re.Match] | None:
    if re.search(r"\b(laptop|notebook|riser|bracket|holder|backplate|cable)\b", title, re.I):
        return None
    found = gpu_chip(title)
    if not found:
        return None
    chip, match = found
    vram = None
    for m in _VRAM.finditer(title):
        if int(m.group(1)) in _VALID_VRAM:
            vram = int(m.group(1))
            break
    ref = GPUS.get(chip)
    specs["chip"] = pretty_chip(chip)
    if ref:
        default_vram, power, score, maker = ref
        specs.update(chip_maker=maker, tdp_w=power, score=score)
        vram = vram or default_vram
    else:
        specs["chip_maker"] = "nvidia" if chip.startswith(("rtx", "gtx", "gt")) else ("amd" if chip.startswith("rx") else "intel")
    if vram:
        specs["vram_gb"] = vram
    return chip, vram, match


# --------------------------------------------------------------------------- motherboard
_CHIPSET = re.compile(r"(?<![a-z0-9])([abhxzw])(\d{3})(e?)([mi]?)(?![a-z0-9])", re.I)
_SOCKET = re.compile(r"\b(am5|am4|lga\s?-?(?:1851|1700|1200|1151))\b", re.I)


def _parse_motherboard(title: str, specs: dict, flags: set[str]) -> str | None:
    low = title.lower()
    chipset = None
    form_hint = ""
    for m in _CHIPSET.finditer(low):
        cand = f"{m.group(1)}{m.group(2)}{m.group(3)}"
        if cand in CHIPSET_SOCKET:
            chipset, form_hint = cand, m.group(4)
            break
    socket = CHIPSET_SOCKET.get(chipset) if chipset else None
    if not socket and (sm := _SOCKET.search(low)):
        socket = re.sub(r"[\s-]", "", sm.group(1)).upper()
    if not chipset and not socket:
        return None
    if chipset:
        specs["chipset"] = chipset.upper()
    if socket:
        specs["socket"] = socket

    if re.search(r"\bddr4\b|(?<![a-z0-9])d4(?![a-z0-9])", low):
        specs["memory_type"] = "DDR4"
        flags.add("ddr4")
    elif re.search(r"\bddr5\b|(?<![a-z0-9])d5(?![a-z0-9])", low) or socket in DDR5_ONLY_SOCKETS:
        specs["memory_type"] = "DDR5"
    elif socket in DDR4_ONLY_SOCKETS:
        specs["memory_type"] = "DDR4"

    if re.search(r"e-?atx", low):
        form = "E-ATX"
    elif form_hint == "i" or re.search(r"mini[\s-]?itx|\bitx\b", low):
        form = "Mini-ITX"
    elif form_hint == "m" or re.search(r"micro[\s-]?atx|\bm-?atx\b|\bmatx\b", low):
        form = "Micro-ATX"
    else:
        form = "ATX"
    specs["form_factor"] = form
    if form != "ATX":
        flags.add(form.lower())
    if re.search(r"wifi|wi-fi|wireless|\bax\b|\bbe\b", low):
        specs["wifi"] = True
        flags.add("wifi")
    else:
        specs["wifi"] = False
    return chipset or socket.lower()


# --------------------------------------------------------------------------- RAM
def _parse_ram(title: str, specs: dict) -> str | None:
    low = tidy(title).lower()
    if re.search(r"so-?dimm|laptop|notebook", low):
        return None
    mtype = None
    if m := re.search(r"ddr\s?([345])", low):
        mtype = f"DDR{m.group(1)}"
    elif m := re.search(r"(?<![a-z0-9])d([45])(?![a-z0-9])", low):
        mtype = f"DDR{m.group(1)}"
    modules = per = None
    if m := re.search(r"(?<![0-9])(\d)\s*[x\*]\s*(\d{1,3})\s*gb?", low):
        modules, per = int(m.group(1)), int(m.group(2))
    elif m := re.search(r"(\d{1,3})\s*gb?\s*[x\*]\s*(\d)(?![0-9])", low):
        per, modules = int(m.group(1)), int(m.group(2))
    total = None
    if m := re.search(r"(?<![0-9x])(\d{1,3})\s*gb", low):
        total = int(m.group(1))
    if modules and per:
        total = modules * per
    elif total:
        modules, per = (2, total // 2) if re.search(r"\bkit\b|dual", low) and total >= 16 else (1, total)
    if not total:
        return None
    speed = None
    if m := re.search(r"(\d{4,5})\s*(?:mhz|mt/?s|mts)", low) or re.search(r"ddr[45][\s-](\d{4,5})", low):
        speed = int(m.group(1))
    elif m := re.search(r"(?<![0-9])(\d{4})(?![0-9])", low):
        if 2133 <= int(m.group(1)) <= 9600:
            speed = int(m.group(1))
    if not mtype and speed:
        mtype = "DDR5" if speed >= 4800 else "DDR4"
    specs.update(memory_type=mtype, capacity_gb=total, modules=modules, module_gb=per)
    if speed:
        specs["speed_mhz"] = speed
    if m := re.search(r"(?<![a-z0-9])c(?:l)?\s?(\d{2})(?![0-9])", low):
        specs["cas_latency"] = int(m.group(1))
    specs["rgb"] = bool(re.search(r"\b(a?rgb)\b", low))
    return f"{(mtype or '?').lower()}|{total}|{modules}|{speed or '?'}"


# --------------------------------------------------------------------------- storage
_NOT_INTERNAL_STORAGE = re.compile(
    r"external|portable|\busb\b|flash\s?drive|memory\s?card|micro\s?sd|\bsd\s?card|enclosure|"
    r"docking|adapter|card\s?reader|\bnas\b(?!.*\bhdd\b)|case\s+for", re.I
)


_STANDARD_CAPACITIES = {120, 128, 240, 250, 256, 480, 500, 512, 960, 1000, 1024, 2000, 2048, 4000, 4096}
# SATA SSDs that come in an M.2 or 2.5" shape - "M.2" alone does not mean NVMe.
_SATA_MODELS = re.compile(r"\b(a400|kc600|mx500|bx500|870\s?evo|860\s?evo|su650|su630|sa400|ultra\s?3d|wd\s?blue\s?sa510|sa510|p210)\b", re.I)


def _parse_storage(title: str, specs: dict, flags: set[str]) -> str | None:
    low = tidy(title).lower()
    if _NOT_INTERNAL_STORAGE.search(low):
        return None
    caps = []
    for m in re.finditer(r"(?<![0-9.])(\d+(?:\.\d+)?)\s*(tb|gb)(?![a-z])", low):
        gb = float(m.group(1)) * (1000 if m.group(2) == "tb" else 1)
        if 60 <= gb <= 30000:
            caps.append(int(gb))
    if not caps:  # "SHFR200/960g", "1024G", "WD 500 Blue"
        caps = [int(m.group(1)) for m in re.finditer(r"(?<![0-9a-z])(\d{3,4})g?(?![0-9a-z])", low)
                if int(m.group(1)) in _STANDARD_CAPACITIES]
    if not caps:
        return None
    capacity = max(caps)
    capacity = {1024: 1000, 2048: 2000, 4096: 4000}.get(capacity, capacity)
    if _SATA_MODELS.search(low) and not re.search(r"nvme|pcie", low):
        kind = "SATA SSD"
    elif re.search(r"nvme|pcie|gen\s?[345]", low):
        kind = "NVMe SSD"
    elif re.search(r"\bhdd\b|hard\s?(?:disk|drive)|\d{4,5}\s?rpm|barracuda|ironwolf|skyhawk", low):
        kind = "HDD"
    elif re.search(r"sata|2\.5", low):
        kind = "SATA SSD"
    elif "m.2" in low or "m2" in low:
        kind = "NVMe SSD"
    else:
        kind = "SSD"
    specs.update(storage_type=kind, capacity_gb=capacity)
    if m := re.search(r"gen\s?([345])|pcie\s?([345])(?:\.0)?", low):
        specs["pcie_gen"] = int(m.group(1) or m.group(2))
    if "heatsink" in low or "heat sink" in low:
        flags.add("heatsink")
    return f"{kind.lower()}|{capacity}"


# --------------------------------------------------------------------------- PSU
_NOT_PSU = re.compile(r"\bups\b|power\s?bank|adapter|cable|extension|surge|charger|laptop", re.I)


def _parse_psu(title: str, specs: dict) -> str | None:
    low = tidy(title).lower()
    if _NOT_PSU.search(low):
        return None
    watts = [int(m.group(1)) for m in re.finditer(r"(?<![0-9])(\d{3,4})\s*w(?:att)?s?(?![a-z0-9])", low)]
    watts = [w for w in watts if 250 <= w <= 2000]
    if not watts:  # model codes such as RM850e / GX-750 / MWE 650
        watts = [int(n) for n in re.findall(r"(?<![0-9])(\d{3,4})(?![0-9])", low) if 300 <= int(n) <= 2000 and int(n) % 50 == 0]
    if not watts:
        return None
    wattage = max(watts)
    specs["wattage"] = wattage
    if m := re.search(r"(titanium|platinum|gold|silver|bronze)", low):
        specs["efficiency"] = f"80+ {m.group(1).capitalize()}"
    elif re.search(r"80\s?\+|80\s?plus", low):
        specs["efficiency"] = "80+ White"
    if re.search(r"full(?:y)?[\s-]?modular", low):
        specs["modular"] = "Full"
    elif re.search(r"semi[\s-]?modular", low):
        specs["modular"] = "Semi"
    elif re.search(r"non[\s-]?modular", low):
        specs["modular"] = "No"
    if re.search(r"atx\s?3\.?[01]", low):
        specs["atx3"] = True
    specs["form_factor"] = "SFX" if re.search(r"\bsfx", low) else "ATX"
    return f"{wattage}|{specs['form_factor'].lower()}"


# --------------------------------------------------------------------------- case
_CASE_WORDS = re.compile(r"\b(case|chassis|tower|cube)\b", re.I)
_NOT_CASE = re.compile(r"\b(fans?|riser|cable|bracket|holder|stand|panel|filter|hub|controller|strip|kit)\b", re.I)


def _parse_case(title: str, specs: dict) -> str | None:
    low = tidy(title).lower()
    if not _CASE_WORDS.search(low) and _NOT_CASE.search(low):
        return None
    mentions_itx = re.search(r"mini[\s-]?itx|\bitx\b", low)
    # "atx" / "m-atx" / "e-atx" anywhere else means the case also takes bigger boards
    mentions_bigger = re.search(r"(?<![a-z])(?:e-?)?atx\b", re.sub(r"mini[\s-]?itx", " ", low))
    if re.search(r"full[\s-]?tower", low):
        form, supports = "Full Tower", ["E-ATX", "ATX", "Micro-ATX", "Mini-ITX"]
    elif mentions_itx and not mentions_bigger:
        form, supports = "Mini-ITX", ["Mini-ITX"]
    elif re.search(r"micro[\s-]?atx|\bm-?atx\b|\bmatx\b|mini[\s-]?tower", low):
        form, supports = "Micro-ATX", ["Micro-ATX", "Mini-ITX"]
    else:
        form, supports = "Mid Tower", ["ATX", "Micro-ATX", "Mini-ITX"]
        if re.search(r"e-?atx", low):
            supports = ["E-ATX", *supports]
    specs.update(form_factor=form, supports=supports)
    specs["glass"] = bool(re.search(r"glass|\btg\b", low))
    return "case"


# --------------------------------------------------------------------------- cooler
_NOT_COOLER = re.compile(
    r"thermal\s?(?:paste|compound|pad|grease)|fan\s?hub|controller|bracket|mount(?:ing)?\s?kit|"
    r"backplate|contact\s?frame|laptop|cooling\s?pad|ssd\s?heatsink|\bm\.?2\b", re.I
)
_COOLER_WORDS = re.compile(r"\b(cpu|cooler|tower|liquid|aio|heatsink|radiator|freezer|kraken|assassin|spirit|pump)\b", re.I)


def _parse_cooler(title: str, specs: dict) -> str | None:
    low = tidy(title).lower()
    if _NOT_COOLER.search(low):
        return None
    if re.search(r"\bfans?\b", low) and not _COOLER_WORDS.search(low):
        return None  # plain case fans
    liquid = bool(re.search(r"liquid|\baio\b|all[\s-]in[\s-]one|water|radiator|kraken|pump", low))
    radiator = None
    if liquid:
        if m := re.search(r"(?<![0-9])(120|140|240|280|360|420)\s?mm", low) or re.search(r"(?<![0-9])(240|280|360|420)(?![0-9])", low):
            radiator = int(m.group(1))
    specs["cooler_type"] = "Liquid" if liquid else "Air"
    if radiator:
        specs["radiator_mm"] = radiator
    if m := re.search(r"(?<![0-9])(\d{3})\s?w(?![a-z0-9])", low):
        if 65 <= int(m.group(1)) <= 400:
            specs["tdp_rating_w"] = int(m.group(1))
    return f"{'liquid' if liquid else 'air'}|{radiator or '-'}"


# --------------------------------------------------------------------------- main entry
# Colour editions are separate SKUs (Gigabyte calls its white edition "ICE", MSI "Snow").
_COLOR = re.compile(r"\b(white|pink|silver|ice|snow)\b", re.I)


def parse_part(title: str, category: str, brand_hint: str | None = None) -> ParsedPart | None:
    clean = tidy(title)
    specs: dict = {}
    flags: set[str] = set()
    brand = detect_brand(clean, category) or normalize_brand(brand_hint)
    name = display_name(clean)
    remove_spans: list[str] = []  # substrings that are already captured in the key

    if category == "cpu":
        found = _parse_cpu(clean, specs)
        if not found:
            return None
        maker, model = found
        brand = maker
        name = f"{maker} {specs['model']}"
        key = f"cpu|{maker.lower()}|{model}"
        return ParsedPart(category, brand, name, key, "", frozenset(), frozenset(), specs)

    if category == "gpu":
        found = _parse_gpu(clean, specs)
        if not found:
            return None
        chip, vram, match = found
        remove_spans.append(match.group(0))
        for mod in _GPU_MODIFIERS.findall(name.lower()):
            flags.add(f"mod:{mod.replace(' ', '')}")
        key_tail = f"{chip}|{vram or '?'}"
    elif category == "motherboard":
        primary = _parse_motherboard(clean, specs, flags)
        if not primary:
            return None
        key_tail = primary
    elif category == "ram":
        primary = _parse_ram(clean, specs)
        if not primary:
            return None
        key_tail = primary
    elif category == "storage":
        primary = _parse_storage(clean, specs, flags)
        if not primary:
            return None
        key_tail = primary
    elif category == "psu":
        primary = _parse_psu(clean, specs)
        if not primary:
            return None
        key_tail = primary
    elif category == "case":
        if not _parse_case(clean, specs):
            return None
        key_tail = "case"
    elif category == "cooler":
        primary = _parse_cooler(clean, specs)
        if not primary:
            return None
        key_tail = primary
    else:
        return None

    if m := _COLOR.search(clean):
        flags.add(f"color:{m.group(1).lower()}")
        specs["color"] = m.group(1).capitalize()
        if specs["color"].lower() not in name.lower():
            name = f"{name} ({specs['color']})"  # keep colour editions apart in the UI

    # Model words / codes come from the display name (marketing tail removed).
    model_text = name
    for span in remove_spans:
        model_text = model_text.replace(span, " ")
    spec_values = {str(v) for v in specs.values() if isinstance(v, int | float) and not isinstance(v, bool)}
    skip = _STOPWORDS | _brand_tokens(brand) | {"wifi", "white", "pink", "silver", "ice", "snow"}
    words, codes = [], set()
    for tok in tokens(model_text):
        if tok in skip:
            continue
        if any(ch.isdigit() for ch in tok):
            if not _SPEC_TOKEN.match(tok) and tok not in spec_values:
                codes.add(tok)
        elif len(tok) > 1 or tok in ("x", "a", "e", "f", "i", "p", "v"):
            words.append(tok)

    if brand and not name.lower().startswith(brand.lower()) and brand.lower() not in name.lower():
        name = f"{brand} {name}"
    key = f"{category}|{(brand or '?').lower()}|{key_tail}"
    return ParsedPart(category, brand, name[:300], key[:200], " ".join(words), frozenset(codes), frozenset(flags), specs)
