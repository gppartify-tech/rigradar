"""Reference data for CPUs and GPUs.

Store titles tell us the model ("Ryzen 7 7800X3D", "RTX 5070 Ti") but not how fast it
is or how much power it draws. This table fills that gap for the compatibility
checker (sockets, wattage) and the build recommender (performance per JOD).

The scores are APPROXIMATE relative indexes compiled from public review averages:
  gpu score   : 1440p gaming performance, RTX 5090 = 100
  cpu gaming  : gaming performance with a fast GPU, Ryzen 7 9800X3D = 100
  cpu multi   : multi-threaded performance (rendering/compiling), Ryzen 9 9950X = 100
They are good enough to rank parts against each other, not to quote as benchmarks.
Students: refine these numbers with your own benchmark sources if you have time!
"""

# chip: (default VRAM GB, board power W, score, maker)
GPUS: dict[str, tuple[int, int, float, str]] = {
    # NVIDIA RTX 50 (2025)
    "rtx 5090": (32, 575, 100, "nvidia"),
    "rtx 5080": (16, 360, 66, "nvidia"),
    "rtx 5070 ti": (16, 300, 57, "nvidia"),
    "rtx 5070": (12, 250, 46, "nvidia"),
    "rtx 5060 ti": (16, 180, 34, "nvidia"),
    "rtx 5060": (8, 145, 28, "nvidia"),
    "rtx 5050": (8, 130, 21, "nvidia"),
    # NVIDIA RTX 40
    "rtx 4090": (24, 450, 80, "nvidia"),
    "rtx 4080 super": (16, 320, 61, "nvidia"),
    "rtx 4080": (16, 320, 60, "nvidia"),
    "rtx 4070 ti super": (16, 285, 51, "nvidia"),
    "rtx 4070 ti": (12, 285, 47, "nvidia"),
    "rtx 4070 super": (12, 220, 45, "nvidia"),
    "rtx 4070": (12, 200, 39, "nvidia"),
    "rtx 4060 ti": (8, 160, 30, "nvidia"),
    "rtx 4060": (8, 115, 24, "nvidia"),
    # NVIDIA RTX 30 / GTX 16 / GT
    "rtx 3090 ti": (24, 450, 52, "nvidia"),
    "rtx 3090": (24, 350, 48, "nvidia"),
    "rtx 3080 ti": (12, 350, 46, "nvidia"),
    "rtx 3080": (10, 320, 42, "nvidia"),
    "rtx 3070 ti": (8, 290, 35, "nvidia"),
    "rtx 3070": (8, 220, 33, "nvidia"),
    "rtx 3060 ti": (8, 200, 28, "nvidia"),
    "rtx 3060": (12, 170, 21, "nvidia"),
    "rtx 3050": (8, 130, 13, "nvidia"),
    "gtx 1660 super": (6, 125, 12, "nvidia"),
    "gtx 1660 ti": (6, 120, 12, "nvidia"),
    "gtx 1660": (6, 120, 11, "nvidia"),
    "gtx 1650 super": (4, 100, 9, "nvidia"),
    "gtx 1650": (4, 75, 7, "nvidia"),
    "gtx 1630": (4, 75, 4, "nvidia"),
    "gt 1030": (2, 30, 2, "nvidia"),
    "gt 730": (2, 38, 1, "nvidia"),
    "gt 710": (2, 19, 1, "nvidia"),
    "gt 610": (2, 29, 0.5, "nvidia"),
    # AMD Radeon RX 9000 (2025)
    "rx 9070 xt": (16, 304, 55, "amd"),
    "rx 9070": (16, 220, 49, "amd"),
    "rx 9060 xt": (16, 160, 31, "amd"),
    "rx 9060": (8, 132, 26, "amd"),
    # AMD Radeon RX 7000 / 6000
    "rx 7900 xtx": (24, 355, 59, "amd"),
    "rx 7900 xt": (20, 315, 52, "amd"),
    "rx 7900 gre": (16, 260, 44, "amd"),
    "rx 7800 xt": (16, 263, 41, "amd"),
    "rx 7700 xt": (12, 245, 35, "amd"),
    "rx 7600 xt": (16, 190, 24, "amd"),
    "rx 7600": (8, 165, 23, "amd"),
    "rx 6950 xt": (16, 335, 45, "amd"),
    "rx 6900 xt": (16, 300, 42, "amd"),
    "rx 6800 xt": (16, 300, 40, "amd"),
    "rx 6800": (16, 250, 35, "amd"),
    "rx 6750 xt": (12, 250, 30, "amd"),
    "rx 6700 xt": (12, 230, 28, "amd"),
    "rx 6650 xt": (8, 180, 22, "amd"),
    "rx 6600 xt": (8, 160, 21, "amd"),
    "rx 6600": (8, 132, 18, "amd"),
    "rx 6500 xt": (4, 107, 8, "amd"),
    "rx 6400": (4, 53, 6, "amd"),
    "rx 580": (8, 185, 9, "amd"),
    # Intel Arc
    "arc b580": (12, 190, 27, "intel"),
    "arc b570": (10, 150, 23, "intel"),
    "arc a770": (16, 225, 21, "intel"),
    "arc a750": (8, 225, 19, "intel"),
    "arc a580": (8, 185, 16, "intel"),
    "arc a380": (6, 75, 6, "intel"),
}

# model: (cores, threads, boost GHz, typical max power W, socket, has iGPU, gaming, multi)
_CPU_BASE: dict[str, tuple[int, int, float, int, str, bool, float, float]] = {
    # AMD AM5 - Ryzen 9000 / 7000 / 8000
    "ryzen 9 9950x3d": (16, 32, 5.7, 170, "AM5", True, 99, 98),
    "ryzen 9 9950x": (16, 32, 5.7, 200, "AM5", True, 86, 100),
    "ryzen 9 9900x3d": (12, 24, 5.5, 120, "AM5", True, 90, 75),
    "ryzen 9 9900x": (12, 24, 5.6, 162, "AM5", True, 84, 76),
    "ryzen 7 9850x3d": (8, 16, 5.6, 120, "AM5", True, 101, 52),
    "ryzen 7 9800x3d": (8, 16, 5.2, 120, "AM5", True, 100, 50),
    "ryzen 7 9700x": (8, 16, 5.5, 88, "AM5", True, 80, 46),
    "ryzen 5 9600x": (6, 12, 5.4, 88, "AM5", True, 77, 37),
    "ryzen 5 9600": (6, 12, 5.2, 88, "AM5", True, 75, 35),
    "ryzen 9 7950x3d": (16, 32, 5.7, 162, "AM5", True, 90, 86),
    "ryzen 9 7950x": (16, 32, 5.7, 230, "AM5", True, 82, 90),
    "ryzen 9 7900x3d": (12, 24, 5.6, 162, "AM5", True, 84, 66),
    "ryzen 9 7900x": (12, 24, 5.6, 230, "AM5", True, 80, 68),
    "ryzen 9 7900": (12, 24, 5.4, 88, "AM5", True, 78, 63),
    "ryzen 7 7800x3d": (8, 16, 5.0, 120, "AM5", True, 90, 42),
    "ryzen 7 7700x": (8, 16, 5.4, 142, "AM5", True, 76, 45),
    "ryzen 7 7700": (8, 16, 5.3, 88, "AM5", True, 75, 43),
    "ryzen 5 7600x": (6, 12, 5.3, 142, "AM5", True, 73, 35),
    "ryzen 5 7600": (6, 12, 5.1, 88, "AM5", True, 71, 33),
    "ryzen 5 7500f": (6, 12, 5.0, 88, "AM5", False, 69, 32),
    "ryzen 5 7400f": (6, 12, 4.7, 88, "AM5", False, 66, 30),
    "ryzen 7 8700g": (8, 16, 5.1, 88, "AM5", True, 66, 40),
    "ryzen 7 8700f": (8, 16, 5.0, 88, "AM5", False, 67, 40),
    "ryzen 5 8600g": (6, 12, 5.0, 88, "AM5", True, 62, 31),
    "ryzen 5 8500g": (6, 12, 5.0, 88, "AM5", True, 56, 26),
    "ryzen 5 8400f": (6, 12, 4.7, 88, "AM5", False, 60, 29),
    # AMD AM4 - Ryzen 5000 / 4000 / 3000
    "ryzen 7 5800x3d": (8, 16, 4.5, 142, "AM4", False, 74, 33),
    "ryzen 7 5700x3d": (8, 16, 4.1, 142, "AM4", False, 70, 31),
    "ryzen 9 5950x": (16, 32, 4.9, 142, "AM4", False, 66, 60),
    "ryzen 9 5900x": (12, 24, 4.8, 142, "AM4", False, 65, 50),
    "ryzen 9 5900xt": (16, 32, 4.8, 142, "AM4", False, 66, 59),
    "ryzen 7 5800x": (8, 16, 4.7, 142, "AM4", False, 64, 36),
    "ryzen 7 5800xt": (8, 16, 4.8, 142, "AM4", False, 65, 37),
    "ryzen 7 5700x": (8, 16, 4.6, 76, "AM4", False, 62, 34),
    "ryzen 7 5700": (8, 16, 4.6, 88, "AM4", False, 58, 32),
    "ryzen 5 5600x": (6, 12, 4.6, 88, "AM4", False, 61, 27),
    "ryzen 5 5600": (6, 12, 4.4, 88, "AM4", False, 59, 26),
    "ryzen 5 5500": (6, 12, 4.2, 88, "AM4", False, 52, 24),
    "ryzen 7 5700g": (8, 16, 4.6, 88, "AM4", True, 55, 32),
    "ryzen 5 5600gt": (6, 12, 4.6, 88, "AM4", True, 52, 26),
    "ryzen 5 5600g": (6, 12, 4.4, 88, "AM4", True, 51, 25),
    "ryzen 5 5500gt": (6, 12, 4.4, 88, "AM4", True, 49, 24),
    "ryzen 5 4600g": (6, 12, 4.2, 88, "AM4", True, 44, 20),
    "ryzen 5 4500": (6, 12, 4.1, 88, "AM4", False, 45, 20),
    "ryzen 3 4100": (4, 8, 4.0, 88, "AM4", False, 38, 13),
    "ryzen 5 3600": (6, 12, 4.2, 88, "AM4", False, 48, 22),
    # Intel LGA1851 - Core Ultra 200S (+ 2026 "Plus" refresh)
    "core ultra 9 285k": (24, 24, 5.7, 250, "LGA1851", True, 84, 95),
    "core ultra 7 270k plus": (24, 24, 5.5, 250, "LGA1851", True, 83, 88),
    "core ultra 7 265k": (20, 20, 5.5, 250, "LGA1851", True, 81, 82),
    "core ultra 7 265": (20, 20, 5.3, 182, "LGA1851", True, 78, 74),
    "core ultra 5 250k plus": (18, 18, 5.3, 159, "LGA1851", True, 77, 66),
    "core ultra 5 245k": (14, 14, 5.2, 159, "LGA1851", True, 75, 58),
    "core ultra 5 235": (14, 14, 5.0, 121, "LGA1851", True, 70, 52),
    "core ultra 5 225": (10, 10, 4.9, 121, "LGA1851", True, 66, 42),
    # Intel LGA1700 - 12th / 13th / 14th gen
    "core i9-14900k": (24, 32, 6.0, 253, "LGA1700", True, 86, 92),
    "core i9-14900": (24, 32, 5.8, 219, "LGA1700", True, 82, 84),
    "core i7-14700k": (20, 28, 5.6, 253, "LGA1700", True, 84, 82),
    "core i7-14700": (20, 28, 5.4, 219, "LGA1700", True, 80, 74),
    "core i5-14600k": (14, 20, 5.3, 181, "LGA1700", True, 78, 58),
    "core i5-14500": (14, 20, 5.0, 154, "LGA1700", True, 72, 50),
    "core i5-14400": (10, 16, 4.7, 148, "LGA1700", True, 68, 40),
    "core i3-14100": (4, 8, 4.7, 110, "LGA1700", True, 57, 20),
    "core i9-13900k": (24, 32, 5.8, 253, "LGA1700", True, 85, 88),
    "core i7-13700k": (16, 24, 5.4, 253, "LGA1700", True, 81, 72),
    "core i7-13700": (16, 24, 5.2, 219, "LGA1700", True, 78, 66),
    "core i5-13600k": (14, 20, 5.1, 181, "LGA1700", True, 77, 55),
    "core i5-13400": (10, 16, 4.6, 148, "LGA1700", True, 65, 37),
    "core i3-13100": (4, 8, 4.5, 89, "LGA1700", True, 55, 19),
    "core i9-12900k": (16, 24, 5.2, 241, "LGA1700", True, 78, 62),
    "core i7-12700k": (12, 20, 5.0, 190, "LGA1700", True, 76, 52),
    "core i7-12700": (12, 20, 4.9, 180, "LGA1700", True, 73, 46),
    "core i5-12600k": (10, 16, 4.9, 150, "LGA1700", True, 72, 42),
    "core i5-12400": (6, 12, 4.4, 117, "LGA1700", True, 62, 30),
    "core i3-12100": (4, 8, 4.3, 89, "LGA1700", True, 52, 18),
    # Intel LGA1200 / LGA1151 (older, still sold)
    "core i7-10700k": (8, 16, 5.1, 125, "LGA1200", True, 56, 33),
    "core i5-11400": (6, 12, 4.4, 65, "LGA1200", True, 52, 25),
    "core i5-10400": (6, 12, 4.3, 65, "LGA1200", True, 48, 22),
    "core i3-10100": (4, 8, 4.3, 65, "LGA1200", True, 40, 13),
    "core i9-9900k": (8, 16, 5.0, 95, "LGA1151", True, 55, 32),
    "core i7-9700k": (8, 8, 4.9, 95, "LGA1151", True, 52, 27),
    "core i5-9400": (6, 6, 4.1, 65, "LGA1151", True, 42, 17),
}


def _with_f_variants(base: dict) -> dict:
    """Intel 'F'/'KF' and AMD-style variants are identical except for the missing iGPU."""
    out = dict(base)
    for model, spec in base.items():
        if model.startswith("core ") and spec[5]:
            no_igpu = spec[:5] + (False,) + spec[6:]
            if model.endswith(" plus"):
                out.setdefault(model.replace("k plus", "kf plus"), no_igpu)
            else:
                out.setdefault(model + "f", no_igpu)
    return out


CPUS = _with_f_variants(_CPU_BASE)

# Motherboard chipset -> socket
CHIPSET_SOCKET: dict[str, str] = {
    **{c: "AM5" for c in ("a620", "b650", "b650e", "b840", "b850", "x670", "x670e", "x870", "x870e")},
    **{c: "AM4" for c in ("a320", "a520", "b350", "b450", "b550", "x370", "x470", "x570")},
    **{c: "LGA1851" for c in ("h810", "b860", "z890", "w880")},
    **{c: "LGA1700" for c in ("h610", "b660", "h670", "z690", "b760", "h770", "z790", "w680")},
    **{c: "LGA1200" for c in ("h410", "b460", "h470", "z490", "h510", "b560", "h570", "z590")},
    **{c: "LGA1151" for c in ("h310", "b360", "b365", "h370", "z370", "z390")},
}
DDR5_ONLY_SOCKETS = {"AM5", "LGA1851"}
DDR4_ONLY_SOCKETS = {"AM4", "LGA1200", "LGA1151"}

# Older GPUs that are still sold (mostly second-hand / clearance)
GPUS.update({
    "rtx 2080 ti": (11, 250, 33, "nvidia"),
    "rtx 2080 super": (8, 250, 29, "nvidia"),
    "rtx 2080": (8, 215, 27, "nvidia"),
    "rtx 2070 super": (8, 215, 25, "nvidia"),
    "rtx 2070": (8, 175, 22, "nvidia"),
    "rtx 2060 super": (8, 175, 20, "nvidia"),
    "rtx 2060": (6, 160, 17, "nvidia"),
    "gtx 1080 ti": (11, 250, 22, "nvidia"),
    "gtx 1080": (8, 180, 17, "nvidia"),
    "gtx 1070 ti": (8, 180, 15, "nvidia"),
    "gtx 1070": (8, 150, 14, "nvidia"),
    "gtx 1060": (6, 120, 10, "nvidia"),
    "gtx 1050 ti": (4, 75, 6, "nvidia"),
    "gtx 1050": (2, 75, 5, "nvidia"),
})
# 2026 dual-cache Ryzen
CPUS["ryzen 9 9950x3d2"] = (16, 32, 5.6, 200, "AM5", True, 100, 99)
