import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { ArrowRight, BadgePercent, Bell, Bot, Radar, Search, ShoppingBag, Sparkles, Wrench } from "lucide-react";
import { ProductCard } from "../components/ProductCard";
import { ProductImage, StoreBadge } from "../components/ui";
import { CATEGORIES, CONDITIONS, formatPrice, timeAgo, timeAgoShort } from "../lib/format";
import { useApi } from "../lib/useApi";

const QUICK = ["RTX 5060", "RX 9070 XT", "Ryzen 7 7800X3D", "DDR5 32GB", "NVMe 1TB", "B650"];
const PRESETS = [
  { budget: 900, use: "gaming", resolution: "1080p", title: "1080p gaming", text: "Smooth esports & AAA at 1080p" },
  { budget: 1500, use: "gaming", resolution: "1440p", title: "1440p gaming", text: "High settings, high refresh" },
  { budget: 2000, use: "creator", title: "Creator", text: "Editing, 3D and streaming" },
  { budget: 550, use: "office", title: "Study & office", text: "Quiet, efficient, no GPU needed" },
];

function Hero() {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const { data: stores } = useApi("/stores");
  const { data: cats } = useApi("/categories");
  const tracked = (cats || []).reduce((n, c) => n + c.product_count, 0);
  const lastUpdate = (stores || []).map((s) => s.last_scraped_at).filter(Boolean).sort().pop();
  return (
    <section className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white">
      <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-indigo-500/20 blur-3xl" />
      <div className="container-page relative py-14 sm:py-20">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-indigo-100">
            <Radar className="h-3.5 w-3.5" /> Tracking iGeek, CompuJordan & Oriental Store
          </span>
          <h1 className="mt-5 text-4xl font-extrabold tracking-tight sm:text-5xl">
            The best price for every PC part in Jordan
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-300">
            Compare prices across stores, get an alert the moment a part hits your target price, and let the AI assistant
            plan a build that fits your budget.
          </p>
          <form
            className="mt-8 flex max-w-2xl gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (q.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`);
            }}
          >
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                className="w-full rounded-2xl border-0 bg-white dark:bg-slate-900 py-3.5 pl-12 pr-4 text-slate-900 dark:text-slate-50 shadow-lg placeholder:text-slate-400 focus:outline-none focus:ring-4 focus:ring-indigo-400/40"
                placeholder="Search a part, e.g. RTX 5070 Ti"
                aria-label="Search parts"
              />
            </div>
            <button className="btn btn-primary rounded-2xl px-6">Search</button>
          </form>
          <div className="mt-4 flex flex-wrap gap-2">
            {QUICK.map((term) => (
              <Link key={term} to={`/search?q=${encodeURIComponent(term)}`} className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-200 hover:bg-white/20">
                {term}
              </Link>
            ))}
          </div>
          <dl className="mt-10 grid max-w-xl grid-cols-3 gap-6">
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Parts tracked</dt>
              <dd className="mt-1 text-2xl font-bold">{tracked ? tracked.toLocaleString() : "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Stores</dt>
              <dd className="mt-1 text-2xl font-bold">{stores?.length ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs uppercase tracking-wide text-slate-400">Last check</dt>
              <dd className="mt-1 text-2xl font-bold">{lastUpdate ? timeAgoShort(lastUpdate) : "—"}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
}

function Categories() {
  const { data } = useApi("/categories");
  const stats = Object.fromEntries((data || []).map((c) => [c.slug, c]));
  return (
    <section className="container-page mt-12">
      <h2 className="section-title">Browse by category</h2>
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {CATEGORIES.map(({ slug, name, icon: Icon }) => (
          <Link key={slug} to={`/parts/${slug}`} className="card group flex items-center gap-4 p-4 transition hover:border-indigo-200 dark:hover:border-indigo-500/30 hover:shadow-md">
            <span className="rounded-xl bg-indigo-50 dark:bg-indigo-500/10 p-3 text-indigo-600 dark:text-indigo-400 transition group-hover:bg-indigo-600 group-hover:text-white">
              <Icon className="h-6 w-6" />
            </span>
            <div className="min-w-0">
              <div className="font-semibold text-slate-900 dark:text-slate-50">{name}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">
                {stats[slug] ? `${stats[slug].in_stock_count} in stock · from ${formatPrice(stats[slug].min_price)}` : " "}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function Deals() {
  const { data } = useApi("/deals", { limit: 8 });
  if (!data?.length) return null;
  return (
    <section className="container-page mt-14">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <BadgePercent className="h-6 w-6 text-rose-500" /> Best deals right now
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Biggest discounts on in-stock parts (store sales and price drops we tracked).</p>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
        {data.map((deal) => (
          <ProductCard
            key={deal.product.id}
            product={{ ...deal.product, best_price: deal.price, best_store: deal.store }}
            badge={
              <span className="rounded-full bg-rose-600 px-2 py-0.5 text-xs font-bold text-white">
                −{Math.round(deal.drop_pct)}%
              </span>
            }
          />
        ))}
      </div>
    </section>
  );
}

function Features() {
  const items = [
    { icon: Search, title: "Compare 3 stores", text: "One page per part with every store's price and stock, refreshed every few hours." },
    { icon: Bell, title: "Price alerts", text: "Add parts to your wishlist with a target price - we e-mail you when it drops." },
    { icon: Bot, title: "AI build assistant", text: "Describe your budget and games in English or Arabic, get a compatible build." },
    { icon: ShoppingBag, title: "Used marketplace", text: "Sell the parts you upgrade from, or find a bargain from other builders." },
  ];
  return (
    <section className="container-page mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {items.map(({ icon: Icon, title, text }) => (
        <div key={title} className="card p-5">
          <Icon className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
          <h3 className="mt-3 font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{text}</p>
        </div>
      ))}
    </section>
  );
}

function BuildPresets() {
  return (
    <section className="container-page mt-14">
      <div className="card overflow-hidden">
        <div className="grid gap-6 p-6 sm:p-8 lg:grid-cols-[1fr_2fr] lg:items-center">
          <div>
            <h2 className="section-title flex items-center gap-2">
              <Sparkles className="h-6 w-6 text-indigo-600 dark:text-indigo-400" /> Get a build in one click
            </h2>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
              Our recommender splits your budget, checks socket, memory, power and case compatibility, and only picks parts
              that are in stock today.
            </p>
            <Link to="/assistant" className="btn btn-secondary mt-4">
              <Bot className="h-4 w-4" /> Or ask the assistant
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {PRESETS.map((p) => (
              <Link
                key={p.title}
                to={`/builder?budget=${p.budget}&use=${p.use}${p.resolution ? `&res=${p.resolution}` : ""}`}
                className="group flex items-center justify-between rounded-2xl border border-slate-200 dark:border-slate-800 p-4 transition hover:border-indigo-300 dark:hover:border-indigo-500/40 hover:bg-indigo-50/50 dark:hover:bg-indigo-500/10"
              >
                <div>
                  <div className="font-semibold">{p.title}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">{p.text}</div>
                  <div className="mt-1 text-sm font-bold text-indigo-700 dark:text-indigo-300">~{formatPrice(p.budget)}</div>
                </div>
                <Wrench className="h-5 w-5 text-slate-300 transition group-hover:text-indigo-600 dark:group-hover:text-indigo-400" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function LatestListings() {
  const { data } = useApi("/listings", { page_size: 4 });
  if (!data?.items?.length) return null;
  return (
    <section className="container-page mt-14">
      <div className="flex items-end justify-between">
        <h2 className="section-title">Fresh on the marketplace</h2>
        <Link to="/marketplace" className="link flex items-center gap-1 text-sm">
          All listings <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-4 md:grid-cols-4">
        {data.items.map((l) => (
          <Link key={l.id} to={`/marketplace/${l.id}`} className="card overflow-hidden transition hover:shadow-md">
            <ProductImage src={l.cover_image} category={l.category} className="aspect-[4/3] w-full object-cover" />
            <div className="p-3">
              <div className="line-clamp-1 text-sm font-semibold">{l.title}</div>
              <div className="mt-1 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
                <span className="font-bold text-slate-900 dark:text-slate-50">{formatPrice(l.price)}</span>
                <span>{CONDITIONS[l.condition]}</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function StoresStrip() {
  const { data } = useApi("/stores");
  return (
    <section className="container-page mt-14">
      <div className="card flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-slate-600 dark:text-slate-300">Prices are refreshed automatically from:</div>
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {(data || []).map((s) => (
            <div key={s.id} className="flex items-center gap-2">
              <StoreBadge store={s} className="font-semibold" />
              <span className="text-xs text-slate-400">{timeAgo(s.last_scraped_at)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  return (
    <>
      <Hero />
      <Categories />
      <Deals />
      <BuildPresets />
      <Features />
      <LatestListings />
      <StoresStrip />
    </>
  );
}
