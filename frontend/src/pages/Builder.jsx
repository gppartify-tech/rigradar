import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { CheckCircle2, CircleAlert, Heart, Plus, RefreshCw, Search, Share2, Sparkles, Trash2, Zap } from "lucide-react";
import { ErrorBox, IssueList, Modal, ProductImage, Spinner, StockBadge, StoreBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useBuild } from "../lib/build";
import { CATEGORIES, formatPrice, specHighlights } from "../lib/format";
import { useApi } from "../lib/useApi";

const USE_CASES = [
  { value: "gaming", label: "Gaming" },
  { value: "streaming", label: "Gaming + streaming" },
  { value: "creator", label: "Video editing / 3D" },
  { value: "workstation", label: "AI / workstation" },
  { value: "office", label: "Study / office" },
];

// Filters that keep the picker list compatible with what is already chosen.
function compatibleFilters(category, chosen) {
  const cpu = chosen.cpu?.specs, board = chosen.motherboard?.specs;
  if (category === "motherboard" && cpu?.socket) return { spec_socket: cpu.socket, label: `socket ${cpu.socket}` };
  if (category === "cpu" && board?.socket) return { spec_socket: board.socket, label: `socket ${board.socket}` };
  if (category === "ram" && board?.memory_type) return { spec_memory_type: board.memory_type, label: board.memory_type };
  return null;
}

function PartPicker({ category, chosen, onPick, onClose }) {
  const [q, setQ] = useState("");
  const [onlyCompatible, setOnlyCompatible] = useState(true);
  const [page, setPage] = useState(1);
  const compat = compatibleFilters(category.slug, chosen);
  const { label, ...compatParams } = compat || {};
  const { data, loading } = useApi("/products", {
    category: category.slug, q, in_stock: true, sort: "price_asc", page, page_size: 20,
    ...(onlyCompatible && compat ? compatParams : {}),
  });
  return (
    <Modal open onClose={onClose} title={`Choose a ${category.singular.toLowerCase()}`} wide>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input autoFocus className="input pl-9" placeholder="Filter by name…" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      </div>
      {compat && (
        <label className="mt-3 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
          <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={onlyCompatible} onChange={(e) => setOnlyCompatible(e.target.checked)} />
          Only show parts compatible with your build ({label})
        </label>
      )}
      <div className={`mt-4 space-y-2 ${loading ? "opacity-60" : ""}`}>
        {!data && <div className="flex justify-center py-10"><Spinner /></div>}
        {data?.items.length === 0 && <p className="py-8 text-center text-sm text-slate-500 dark:text-slate-400">No in-stock parts match.</p>}
        {data?.items.map((p) => (
          <button key={p.id} onClick={() => onPick(p)} className="flex w-full items-center gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-2.5 text-left transition hover:border-indigo-300 dark:hover:border-indigo-500/40 hover:bg-indigo-50/40 dark:hover:bg-indigo-500/10">
            <ProductImage src={p.image_url} category={p.category} className="h-12 w-12 rounded-lg" />
            <div className="min-w-0 flex-1">
              <div className="line-clamp-1 text-sm font-medium">{p.name}</div>
              <div className="mt-0.5 flex flex-wrap gap-1">
                {specHighlights(p).map((s) => <span key={s} className="chip">{s}</span>)}
              </div>
            </div>
            <div className="text-right">
              <div className="tabular font-bold">{formatPrice(p.best_price)}</div>
              <StoreBadge store={p.best_store} className="text-xs" />
            </div>
          </button>
        ))}
      </div>
      {data && data.pages > 1 && (
        <div className="mt-4 flex justify-between">
          <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span className="text-sm text-slate-500 dark:text-slate-400">Page {page} of {data.pages}</span>
          <button className="btn btn-ghost btn-sm" disabled={page >= data.pages} onClick={() => setPage(page + 1)}>Next</button>
        </div>
      )}
    </Modal>
  );
}

function AutoBuild({ onBuilt }) {
  const [params] = useSearchParams();
  const [form, setForm] = useState({
    budget: params.get("budget") || 1200, use_case: params.get("use") || "gaming",
    resolution: params.get("res") || "1440p", cpu_brand: "any", gpu_brand: "any",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const run = async (values = form) => {
    setBusy(true);
    setError(null);
    try {
      const body = { ...values, budget: Number(values.budget), resolution: values.use_case === "gaming" || values.use_case === "streaming" ? values.resolution : null };
      onBuilt(await api("/builds/recommend", { method: "POST", body }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  // /builder?budget=1500&use=gaming (from the home page) builds straight away
  useEffect(() => {
    if (params.get("budget")) run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  return (
    <form className="card p-5" onSubmit={(e) => { e.preventDefault(); run(); }}>
      <h2 className="flex items-center gap-2 font-semibold"><Sparkles className="h-5 w-5 text-indigo-600 dark:text-indigo-400" /> Auto-build for a budget</h2>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Picks compatible, in-stock parts with the best performance for the money.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <label><span className="label">Budget (JOD)</span><input type="number" min="150" max="20000" className="input" value={form.budget} onChange={set("budget")} required /></label>
        <label><span className="label">Main use</span>
          <select className="input" value={form.use_case} onChange={set("use_case")}>{USE_CASES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}</select>
        </label>
        <label><span className="label">Resolution</span>
          <select className="input" value={form.resolution} onChange={set("resolution")} disabled={!["gaming", "streaming"].includes(form.use_case)}>
            <option value="1080p">1080p</option><option value="1440p">1440p</option><option value="4k">4K</option>
          </select>
        </label>
        <label><span className="label">CPU brand</span>
          <select className="input" value={form.cpu_brand} onChange={set("cpu_brand")}><option value="any">Any</option><option value="amd">AMD</option><option value="intel">Intel</option></select>
        </label>
        <label><span className="label">GPU brand</span>
          <select className="input" value={form.gpu_brand} onChange={set("gpu_brand")}><option value="any">Any</option><option value="nvidia">NVIDIA</option><option value="amd">AMD</option><option value="intel">Intel</option></select>
        </label>
      </div>
      <ErrorBox error={error} className="mt-3" />
      <button className="btn btn-primary mt-4" disabled={busy}>
        {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Generate build
      </button>
    </form>
  );
}

export default function Builder() {
  const { build, setPart, removePart, clear, replace } = useBuild();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [picking, setPicking] = useState(null);
  const [report, setReport] = useState(null);
  const [notes, setNotes] = useState([]);
  const [message, setMessage] = useState(null);
  const ids = useMemo(() => Object.values(build).filter(Boolean), [build]);

  // shared link: /builder?parts=12,40,77
  useEffect(() => {
    const shared = params.get("parts");
    if (!shared) return;
    api("/builds/check", { method: "POST", body: { product_ids: shared.split(",").map(Number).filter(Boolean) } })
      .then((r) => replace(Object.fromEntries(r.parts.map((p) => [p.category, p.product.id]))))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!ids.length) {
      setReport(null);
      return;
    }
    api("/builds/check", { method: "POST", body: { product_ids: ids } }).then(setReport).catch(() => setReport(null));
  }, [ids.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const chosen = Object.fromEntries((report?.parts || []).map((p) => [p.category, p.product]));
  const partFor = (slug) => report?.parts.find((p) => p.category === slug);

  const onBuilt = (rec) => {
    replace(Object.fromEntries(rec.parts.map((p) => [p.category, p.product.id])));
    setNotes(rec.notes);
    setMessage(null);
  };

  const trackAll = async () => {
    if (!user) return setMessage("Log in to add the whole build to your wishlist.");
    await Promise.allSettled(ids.map((id) => api("/wishlist", { method: "POST", body: { product_id: id } })));
    setMessage(`Added ${ids.length} parts to your wishlist - we'll tell you when they get cheaper.`);
  };
  const share = async () => {
    const url = `${window.location.origin}/builder?parts=${ids.join(",")}`;
    try {
      await navigator.clipboard.writeText(url);
      setMessage("Share link copied to the clipboard.");
    } catch {
      setMessage(url);
    }
  };

  return (
    <div className="container-page py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">PC Builder</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Pick parts yourself or auto-build for a budget. We check compatibility as you go.</p>
        </div>
        {ids.length > 0 && (
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-secondary btn-sm" onClick={trackAll}><Heart className="h-4 w-4" /> Track all prices</button>
            <button className="btn btn-secondary btn-sm" onClick={share}><Share2 className="h-4 w-4" /> Share</button>
            <button className="btn btn-danger btn-sm" onClick={() => { clear(); setNotes([]); }}><Trash2 className="h-4 w-4" /> Clear</button>
          </div>
        )}
      </div>
      {message && <div className="mt-4 rounded-xl border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 px-4 py-3 text-sm text-indigo-900 dark:text-indigo-100">{message}</div>}

      <div className="mt-6"><AutoBuild onBuilt={onBuilt} /></div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="card divide-y divide-slate-100 dark:divide-slate-800">
          {CATEGORIES.map((cat) => {
            const part = partFor(cat.slug);
            const Icon = cat.icon;
            return (
              <div key={cat.slug} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
                <div className="flex w-40 shrink-0 items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  <Icon className="h-5 w-5 text-slate-400" /> {cat.singular}
                </div>
                {part ? (
                  <>
                    <div className="flex min-w-0 flex-1 items-center gap-3">
                      <ProductImage src={part.product.image_url} category={cat.slug} className="h-12 w-12 shrink-0 rounded-lg border border-slate-100 dark:border-slate-800" />
                      <div className="min-w-0">
                        <Link to={`/product/${part.product.id}`} className="line-clamp-1 text-sm font-medium hover:text-indigo-700 dark:hover:text-indigo-300">{part.product.name}</Link>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2">
                          <StoreBadge store={part.product.best_store} className="text-xs" />
                          {!part.product.in_stock && <StockBadge inStock={false} />}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between gap-3 sm:justify-end">
                      <span className="tabular font-bold">{formatPrice(part.price)}</span>
                      <div className="flex gap-1">
                        <button className="btn btn-ghost btn-sm" onClick={() => setPicking(cat)}>Change</button>
                        <button className="btn btn-ghost btn-sm" onClick={() => removePart(cat.slug)} aria-label={`Remove ${cat.singular}`}><Trash2 className="h-4 w-4" /></button>
                      </div>
                    </div>
                  </>
                ) : (
                  <button className="btn btn-secondary btn-sm self-start sm:ml-auto" onClick={() => setPicking(cat)}>
                    <Plus className="h-4 w-4" /> Choose {cat.singular.toLowerCase()}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <div className="card p-5">
            <div className="text-sm text-slate-500 dark:text-slate-400">Total</div>
            <div className="text-3xl font-extrabold">{formatPrice(report?.total_price ?? 0)}</div>
            {report && (
              <>
                <div className={`mt-3 flex items-center gap-2 text-sm font-semibold ${report.compatible ? "text-emerald-700 dark:text-emerald-300" : "text-rose-700 dark:text-rose-300"}`}>
                  {report.compatible ? <CheckCircle2 className="h-5 w-5" /> : <CircleAlert className="h-5 w-5" />}
                  {report.compatible ? "No compatibility problems" : "Compatibility problems found"}
                </div>
                <div className="mt-2 flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <Zap className="h-4 w-4 text-amber-500" /> Estimated power ~{report.estimated_wattage} W (PSU {report.recommended_psu_w} W+)
                </div>
              </>
            )}
          </div>
          {report?.issues?.length > 0 && <IssueList issues={report.issues} />}
          {notes.length > 0 && (
            <div className="card p-4 text-sm text-slate-600 dark:text-slate-300">
              <h3 className="mb-2 font-semibold text-slate-900 dark:text-slate-50">How this build was chosen</h3>
              <ul className="list-disc space-y-1 ps-5">{notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
            </div>
          )}
        </aside>
      </div>

      {picking && (
        <PartPicker
          category={picking}
          chosen={chosen}
          onClose={() => setPicking(null)}
          onPick={(p) => { setPart(picking.slug, p.id); setPicking(null); }}
        />
      )}
    </div>
  );
}
