import { useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { PackageSearch, SlidersHorizontal, X } from "lucide-react";
import { ProductRow } from "../components/ProductCard";
import { EmptyState, ErrorBox, Pagination, PageLoader } from "../components/ui";
import { CATEGORY, specLabel, specValue } from "../lib/format";
import { useApi } from "../lib/useApi";

const SORTS = [
  { value: "price_asc", label: "Lowest price" },
  { value: "price_desc", label: "Highest price" },
  { value: "stores", label: "Sold by most stores" },
  { value: "performance", label: "Fastest first", only: ["cpu", "gpu"] },
  { value: "newest", label: "Newest" },
  { value: "name", label: "Name" },
];

function CheckList({ title, values, selected, onToggle, format = (v) => v, limit = 8 }) {
  const [all, setAll] = useState(false);
  if (!values?.length) return null;
  const shown = all ? values : values.slice(0, limit);
  return (
    <fieldset className="border-t border-slate-100 dark:border-slate-800 py-4">
      <legend className="mb-2 text-sm font-semibold text-slate-900 dark:text-slate-50">{title}</legend>
      <div className="space-y-1.5">
        {shown.map(({ value, count }) => (
          <label key={value} className="flex cursor-pointer items-center gap-2 text-sm text-slate-700 dark:text-slate-200">
            <input
              type="checkbox"
              className="h-4 w-4 rounded accent-indigo-600"
              checked={selected.includes(value)}
              onChange={() => onToggle(value)}
            />
            <span className="flex-1 truncate">{format(value)}</span>
            <span className="text-xs text-slate-400">{count}</span>
          </label>
        ))}
      </div>
      {values.length > limit && (
        <button className="mt-2 text-xs font-semibold text-indigo-600 dark:text-indigo-400" onClick={() => setAll((a) => !a)}>
          {all ? "Show less" : `Show all ${values.length}`}
        </button>
      )}
    </fieldset>
  );
}

export default function Browse() {
  const { category } = useParams();
  const [params, setParams] = useSearchParams();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const meta = category ? CATEGORY[category] : null;

  const q = params.get("q") || "";
  const page = Number(params.get("page") || 1);
  const sort = params.get("sort") || "price_asc";
  const inStock = params.get("in_stock") === "true";
  const brands = params.getAll("brand");
  const stores = params.getAll("store");
  const specParams = {};
  for (const [key, value] of params.entries()) {
    if (key.startsWith("spec_")) (specParams[key] ||= []).push(value);
  }

  const query = {
    category, q, page, sort, in_stock: inStock || undefined, brand: brands, store: stores,
    min_price: params.get("min_price") || undefined, max_price: params.get("max_price") || undefined,
    page_size: 24, ...specParams,
  };
  const { data, loading, error } = useApi("/products", query);
  const { data: facets } = useApi(category ? "/products/facets" : null, { category });

  const update = (changes) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      next.delete(key);
      if (Array.isArray(value)) value.forEach((v) => next.append(key, v));
      else if (value !== undefined && value !== null && value !== "" && value !== false) next.set(key, value);
    }
    if (!("page" in changes)) next.delete("page");
    setParams(next);
  };
  const toggle = (key, value) => {
    const current = params.getAll(key);
    update({ [key]: current.includes(value) ? current.filter((v) => v !== value) : [...current, value] });
  };
  const activeFilters = [...params.keys()].filter((k) => !["q", "page", "sort"].includes(k)).length;

  const filters = (
    <div>
      <label className="flex cursor-pointer items-center justify-between py-2 text-sm font-medium">
        In stock only
        <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={inStock} onChange={(e) => update({ in_stock: e.target.checked ? "true" : "" })} />
      </label>
      <fieldset className="border-t border-slate-100 dark:border-slate-800 py-4">
        <legend className="mb-2 text-sm font-semibold text-slate-900 dark:text-slate-50">Price (JOD)</legend>
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            update({ min_price: f.get("min"), max_price: f.get("max") });
          }}
        >
          <input name="min" type="number" min="0" placeholder="Min" defaultValue={params.get("min_price") || ""} className="input py-1.5" />
          <span className="text-slate-400">–</span>
          <input name="max" type="number" min="0" placeholder="Max" defaultValue={params.get("max_price") || ""} className="input py-1.5" />
          <button className="btn btn-secondary btn-sm">Go</button>
        </form>
      </fieldset>
      {facets && (
        <>
          <CheckList title="Store" values={facets.stores} selected={stores} onToggle={(v) => toggle("store", v)}
            format={(v) => ({ igeek: "iGeek Megastore", compujordan: "CompuJordan", oriental: "Oriental Store" })[v] || v} />
          {Object.entries(facets.specs).map(([key, values]) => (
            <CheckList key={key} title={specLabel(key)} values={values} selected={params.getAll(`spec_${key}`)}
              onToggle={(v) => toggle(`spec_${key}`, v)}
              format={(v) => (v === "true" ? "Yes" : v === "false" ? "No" : specValue(key, isNaN(v) ? v : Number(v)))} />
          ))}
          <CheckList title="Brand" values={facets.brands} selected={brands} onToggle={(v) => toggle("brand", v)} />
        </>
      )}
      {activeFilters > 0 && (
        <button className="btn btn-ghost btn-sm mt-2 w-full" onClick={() => setParams(q ? { q } : {})}>
          <X className="h-4 w-4" /> Clear all filters
        </button>
      )}
    </div>
  );

  const title = meta ? meta.name : q ? `Results for “${q}”` : "All parts";
  return (
    <div className="container-page py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {data ? `${data.total.toLocaleString()} products` : " "}
            {meta && " · lowest price across iGeek, CompuJordan and Oriental Store"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {meta && (
            <button className="btn btn-secondary lg:hidden" onClick={() => setFiltersOpen((o) => !o)}>
              <SlidersHorizontal className="h-4 w-4" /> Filters {activeFilters > 0 && `(${activeFilters})`}
            </button>
          )}
          <select className="input w-auto py-2" value={sort} onChange={(e) => update({ sort: e.target.value })} aria-label="Sort by">
            {SORTS.filter((s) => !s.only || s.only.includes(category)).map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        {meta && (
          <aside className={`${filtersOpen ? "block" : "hidden"} lg:block`}>
            <div className="card p-4 lg:sticky lg:top-24">{filters}</div>
          </aside>
        )}
        <section className={`${meta ? "" : "lg:col-span-2"} min-w-0`}>
          <ErrorBox error={error} />
          {!data && loading && <PageLoader />}
          {data && data.items.length === 0 && (
            <EmptyState icon={PackageSearch} title="No parts match">
              Try removing a filter, or search for a shorter name (e.g. “4060” instead of the full model).
            </EmptyState>
          )}
          <div className={`space-y-3 transition-opacity ${loading && data ? "opacity-50" : ""}`}>
            {data?.items.map((p) => <ProductRow key={p.id} product={p} />)}
          </div>
          {data && <Pagination page={data.page} pages={data.pages} onChange={(n) => update({ page: n })} />}
        </section>
      </div>
    </div>
  );
}
