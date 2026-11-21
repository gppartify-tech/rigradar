import { useState } from "react";
import { Link } from "react-router";
import { BellRing, Heart, Target, Trash2, TrendingDown, TrendingUp } from "lucide-react";
import { EmptyState, ErrorBox, PageLoader, ProductImage, StockBadge, StoreBadge } from "../components/ui";
import { api } from "../lib/api";
import { formatPrice, timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";

function TargetEditor({ item, onSaved }) {
  const [value, setValue] = useState(item.target_price ?? "");
  const [saving, setSaving] = useState(false);
  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      onSaved(await api(`/wishlist/${item.id}`, { method: "PATCH", body: { target_price: value === "" ? null : Number(value) } }));
    } finally {
      setSaving(false);
    }
  };
  return (
    <form onSubmit={save} className="flex items-center gap-2">
      <label className="sr-only" htmlFor={`target-${item.id}`}>Target price</label>
      <input id={`target-${item.id}`} type="number" min="1" step="0.5" className="input w-28 py-1.5" placeholder="Target" value={value} onChange={(e) => setValue(e.target.value)} />
      <button className="btn btn-secondary btn-sm" disabled={saving || String(value) === String(item.target_price ?? "")}>Save</button>
    </form>
  );
}

export default function Wishlist() {
  const { data, error, loading, setData } = useApi("/wishlist");
  if (loading && !data) return <PageLoader />;

  const replace = (updated) => setData((items) => items.map((i) => (i.id === updated.id ? updated : i)));
  const remove = async (id) => {
    await api(`/wishlist/${id}`, { method: "DELETE" });
    setData((items) => items.filter((i) => i.id !== id));
  };

  return (
    <div className="container-page py-8">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Wishlist & price alerts</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        We check every store every few hours. When a part reaches your target price you get a notification here and by e-mail.
      </p>
      <ErrorBox error={error} className="mt-4" />
      {data?.length === 0 && (
        <div className="mt-6">
          <EmptyState icon={Heart} title="Nothing tracked yet" action={<Link to="/parts/gpu" className="btn btn-primary">Browse parts</Link>}>
            Open any product and press “Track price” to start getting alerts.
          </EmptyState>
        </div>
      )}
      <div className="mt-6 space-y-3">
        {data?.map((item) => {
          const p = item.product;
          const change = item.price_when_added && p.best_price ? ((p.best_price - item.price_when_added) / item.price_when_added) * 100 : null;
          return (
            <div key={item.id} className="card flex flex-col gap-4 p-4 md:flex-row md:items-center">
              <Link to={`/product/${p.id}`} className="flex min-w-0 flex-1 items-center gap-4">
                <ProductImage src={p.image_url} category={p.category} className="h-16 w-16 shrink-0 rounded-xl border border-slate-100 dark:border-slate-800" />
                <div className="min-w-0">
                  <div className="line-clamp-2 font-semibold hover:text-indigo-700 dark:hover:text-indigo-300">{p.name}</div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <StockBadge inStock={p.in_stock} />
                    <span>added {timeAgo(item.created_at)}</span>
                  </div>
                </div>
              </Link>
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
                <div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">Best price now</div>
                  <div className="tabular text-lg font-bold">{formatPrice(p.best_price)}</div>
                  <StoreBadge store={p.best_store} className="text-xs" />
                </div>
                {change !== null && Math.abs(change) >= 0.5 && (
                  <div className={`flex items-center gap-1 text-sm font-semibold ${change < 0 ? "text-emerald-700 dark:text-emerald-300" : "text-rose-600 dark:text-rose-400"}`}>
                    {change < 0 ? <TrendingDown className="h-4 w-4" /> : <TrendingUp className="h-4 w-4" />}
                    {change > 0 ? "+" : ""}{change.toFixed(1)}% since added
                  </div>
                )}
                <div>
                  <div className="mb-1 flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400"><Target className="h-3.5 w-3.5" /> Alert me at</div>
                  <TargetEditor item={item} onSaved={replace} />
                </div>
                {item.target_reached ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
                    <BellRing className="h-3.5 w-3.5" /> Target reached
                  </span>
                ) : (
                  <span className="chip">{item.target_price ? "Watching" : "Any 5% drop"}</span>
                )}
                <button className="btn btn-ghost btn-sm text-rose-600 dark:text-rose-400" onClick={() => remove(item.id)} aria-label="Remove from wishlist">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
