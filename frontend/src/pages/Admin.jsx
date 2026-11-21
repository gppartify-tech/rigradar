import { useState } from "react";
import { Database, RefreshCw } from "lucide-react";
import { ErrorBox, PageLoader, StoreBadge } from "../components/ui";
import { api } from "../lib/api";
import { formatDate, timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";

const STATUS = {
  success: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  partial: "bg-amber-50 dark:bg-amber-500/10 text-amber-800 dark:text-amber-200",
  failed: "bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300",
  running: "bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300",
};

function duration(run) {
  if (!run.finished_at) return "…";
  const s = Math.round((new Date(run.finished_at) - new Date(run.started_at)) / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;
}

export default function Admin() {
  const { data: stats, reload: reloadStats } = useApi("/admin/stats");
  const { data: runs, reload: reloadRuns, loading } = useApi("/admin/scrape-runs", { limit: 25 });
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const scrape = async (store) => {
    setError(null);
    try {
      const res = await api("/admin/scrape", { method: "POST", body: { store } });
      setMessage(`Scrape queued for ${res.store} (task ${res.task_id.slice(0, 8)}). Refresh in a minute to see the result.`);
      setTimeout(reloadRuns, 1500);
    } catch (err) {
      setError(err);
    }
  };
  if (!stats) return <PageLoader />;
  const tiles = [
    ["Products", stats.products], ["Store offers", stats.offers], ["Price points", stats.price_points],
    ["Users", stats.users], ["Wishlist items", stats.wishlist_items], ["Listings", stats.listings],
  ];

  return (
    <div className="container-page py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight sm:text-3xl"><Database className="h-7 w-7 text-indigo-600 dark:text-indigo-400" /> Admin</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Scraping status and catalog statistics.</p>
        </div>
        <div className="flex gap-2">
          <button className="btn btn-secondary" onClick={() => { reloadRuns(); reloadStats(); }}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh</button>
          <button className="btn btn-primary" onClick={() => scrape(null)}>Scrape all stores now</button>
        </div>
      </div>
      {message && <div className="mt-4 rounded-xl border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 px-4 py-3 text-sm text-indigo-900 dark:text-indigo-100">{message}</div>}
      <ErrorBox error={error} className="mt-4" />

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {tiles.map(([label, value]) => (
          <div key={label} className="card p-4">
            <div className="text-xs text-slate-500 dark:text-slate-400">{label}</div>
            <div className="mt-1 text-2xl font-bold">{value.toLocaleString()}</div>
          </div>
        ))}
      </div>

      <section className="card mt-6 overflow-hidden">
        <h2 className="border-b border-slate-100 dark:border-slate-800 px-5 py-4 font-semibold">Stores</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <tr><th className="px-5 py-2.5">Store</th><th className="px-3 py-2.5 text-right">Active offers</th><th className="px-3 py-2.5 text-right">In stock</th><th className="px-3 py-2.5">Last scraped</th><th className="px-5 py-2.5"></th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {stats.stores.map(({ store, active_offers, in_stock_offers }) => (
                <tr key={store.id}>
                  <td className="px-5 py-3"><StoreBadge store={store} className="font-semibold" /></td>
                  <td className="tabular px-3 py-3 text-right">{active_offers}</td>
                  <td className="tabular px-3 py-3 text-right">{in_stock_offers}</td>
                  <td className="px-3 py-3 text-slate-600 dark:text-slate-300">{timeAgo(store.last_scraped_at)}</td>
                  <td className="px-5 py-3 text-right"><button className="btn btn-secondary btn-sm" onClick={() => scrape(store.slug)}>Scrape now</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card mt-6 overflow-hidden">
        <h2 className="border-b border-slate-100 dark:border-slate-800 px-5 py-4 font-semibold">Recent scrape runs</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
              <tr>
                <th className="px-5 py-2.5">Started</th><th className="px-3 py-2.5">Store</th><th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5 text-right">Pages</th><th className="px-3 py-2.5 text-right">Items</th>
                <th className="px-3 py-2.5 text-right">New offers</th><th className="px-3 py-2.5 text-right">Price changes</th>
                <th className="px-3 py-2.5">Took</th><th className="px-5 py-2.5">Trigger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
              {(runs || []).map((run) => (
                <tr key={run.id} title={run.error_message || ""}>
                  <td className="px-5 py-3 text-slate-600 dark:text-slate-300">{formatDate(run.started_at)} · {new Date(run.started_at).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}</td>
                  <td className="px-3 py-3"><StoreBadge store={run.store} /></td>
                  <td className="px-3 py-3"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS[run.status] || ""}`}>{run.status}</span></td>
                  <td className="tabular px-3 py-3 text-right">{run.pages_fetched}</td>
                  <td className="tabular px-3 py-3 text-right">{run.items_found}</td>
                  <td className="tabular px-3 py-3 text-right">{run.offers_created}</td>
                  <td className="tabular px-3 py-3 text-right">{run.price_changes}</td>
                  <td className="px-3 py-3">{duration(run)}</td>
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400">{run.trigger}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
