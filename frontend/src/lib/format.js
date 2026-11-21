import { Box, CircuitBoard, Cpu, Fan, Gpu, HardDrive, MemoryStick, PlugZap } from "lucide-react";

export const CATEGORIES = [
  { slug: "cpu", name: "Processors", singular: "CPU", icon: Cpu },
  { slug: "gpu", name: "Graphics Cards", singular: "Graphics card", icon: Gpu },
  { slug: "motherboard", name: "Motherboards", singular: "Motherboard", icon: CircuitBoard },
  { slug: "ram", name: "Memory (RAM)", singular: "Memory", icon: MemoryStick },
  { slug: "storage", name: "Storage", singular: "Storage", icon: HardDrive },
  { slug: "psu", name: "Power Supplies", singular: "Power supply", icon: PlugZap },
  { slug: "case", name: "Cases", singular: "Case", icon: Box },
  { slug: "cooler", name: "CPU Coolers", singular: "CPU cooler", icon: Fan },
];
export const CATEGORY = Object.fromEntries(CATEGORIES.map((c) => [c.slug, c]));

export const CONDITIONS = {
  new: "New (sealed)",
  like_new: "Like new",
  good: "Used - good",
  fair: "Used - fair",
  for_parts: "For parts",
};

export function formatPrice(value, { currency = true } = {}) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  const text = number.toLocaleString("en-US", {
    minimumFractionDigits: Number.isInteger(number) ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return currency ? `JOD ${text}` : text;
}

export function timeAgo(iso) {
  if (!iso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  const steps = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [30, "day"],
    [12, "month"],
    [Infinity, "year"],
  ];
  let value = seconds;
  for (const [size, unit] of steps) {
    if (value < size) {
      const n = Math.floor(value);
      if (unit === "second") return "just now";
      return `${n} ${unit}${n === 1 ? "" : "s"} ago`;
    }
    value /= size;
  }
  return "";
}

export function timeAgoShort(iso) {
  if (!iso) return "never";
  const minutes = Math.max(0, (Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${Math.floor(minutes)} min ago`;
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)} h ago`;
  return `${Math.floor(minutes / 1440)} d ago`;
}

export function formatDate(iso) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

// ---- Specs: human labels + formatting --------------------------------------
const gb = (v) => (v >= 1000 ? `${+(v / 1000).toFixed(1)} TB` : `${v} GB`);
const yesNo = (v) => (v ? "Yes" : "No");

export const SPEC_FORMAT = {
  model: ["Model"],
  socket: ["Socket"],
  cores: ["Cores"],
  threads: ["Threads"],
  boost_ghz: ["Boost clock", (v) => `${v} GHz`],
  tdp_w: ["Power draw (est.)", (v) => `${v} W`],
  igpu: ["Integrated graphics", yesNo],
  gaming_score: ["Gaming index", (v) => `${v} / 100`],
  multi_score: ["Multi-core index", (v) => `${v} / 100`],
  packaging: ["Packaging"],
  chip: ["GPU chip"],
  chip_maker: ["GPU maker", (v) => ({ nvidia: "NVIDIA", amd: "AMD", intel: "Intel" })[v] ?? v],
  vram_gb: ["Video memory", (v) => `${v} GB`],
  score: ["Performance index", (v) => `${v} / 100`],
  chipset: ["Chipset"],
  memory_type: ["Memory type"],
  form_factor: ["Form factor"],
  wifi: ["Wi-Fi", yesNo],
  capacity_gb: ["Capacity", gb],
  modules: ["Modules", (v) => `${v} stick${v === 1 ? "" : "s"}`],
  module_gb: ["Per stick", (v) => `${v} GB`],
  speed_mhz: ["Speed", (v) => `${v} MT/s`],
  cas_latency: ["CAS latency", (v) => `CL${v}`],
  rgb: ["RGB lighting", yesNo],
  storage_type: ["Type"],
  pcie_gen: ["PCIe generation", (v) => `Gen ${v}`],
  wattage: ["Wattage", (v) => `${v} W`],
  efficiency: ["Efficiency"],
  modular: ["Modular", (v) => ({ Full: "Fully modular", Semi: "Semi-modular", No: "Non-modular" })[v] ?? v],
  atx3: ["ATX 3.x ready", yesNo],
  supports: ["Fits boards", (v) => (Array.isArray(v) ? v.join(", ") : v)],
  glass: ["Glass side panel", yesNo],
  cooler_type: ["Cooler type"],
  radiator_mm: ["Radiator", (v) => `${v} mm`],
  tdp_rating_w: ["Rated for", (v) => `${v} W`],
  color: ["Colour"],
};

export function specLabel(key) {
  return SPEC_FORMAT[key]?.[0] ?? key.replace(/_/g, " ");
}

export function specValue(key, value) {
  const fmt = SPEC_FORMAT[key]?.[1];
  return fmt ? fmt(value) : String(value);
}

// The 2-4 facts worth showing on a product card, per category.
const HIGHLIGHTS = {
  cpu: ["socket", "cores", "boost_ghz"],
  gpu: ["chip", "vram_gb"],
  motherboard: ["socket", "memory_type", "form_factor", "wifi"],
  ram: ["capacity_gb", "memory_type", "speed_mhz"],
  storage: ["storage_type", "capacity_gb"],
  psu: ["wattage", "efficiency", "modular"],
  case: ["form_factor"],
  cooler: ["cooler_type", "radiator_mm"],
};

export function specHighlights(product) {
  const specs = product?.specs || {};
  return (HIGHLIGHTS[product?.category] || [])
    .filter((k) => specs[k] !== undefined && specs[k] !== null && !(k === "wifi" && !specs[k]))
    .map((k) => (k === "wifi" ? "Wi-Fi" : specValue(k, specs[k])));
}

export function storeDot(store) {
  return store?.color || "#94a3b8";
}
