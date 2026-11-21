import { Link } from "react-router";
import { Bell, BellRing, CheckCheck, PackageCheck, TrendingDown } from "lucide-react";
import { EmptyState, ErrorBox, PageLoader } from "../components/ui";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";

const ICONS = {
  target_reached: [BellRing, "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"],
  price_drop: [TrendingDown, "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-300"],
  back_in_stock: [PackageCheck, "bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300"],
};

export default function Notifications() {
  const { data, error, loading, setData } = useApi("/notifications");
  if (loading && !data) return <PageLoader />;
  const unread = data?.filter((n) => !n.is_read).length || 0;

  const markAll = async () => {
    await api("/notifications/read-all", { method: "POST" });
    setData((list) => list.map((n) => ({ ...n, is_read: true })));
  };
  const markOne = (id) => {
    api(`/notifications/${id}/read`, { method: "POST" }).catch(() => {});
    setData((list) => list.map((n) => (n.id === id ? { ...n, is_read: true } : n)));
  };

  return (
    <div className="container-page max-w-3xl py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Notifications</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{unread} unread</p>
        </div>
        {unread > 0 && (
          <button className="btn btn-secondary btn-sm" onClick={markAll}><CheckCheck className="h-4 w-4" /> Mark all as read</button>
        )}
      </div>
      <ErrorBox error={error} className="mt-4" />
      {data?.length === 0 && (
        <div className="mt-6">
          <EmptyState icon={Bell} title="No notifications yet" action={<Link to="/wishlist" className="btn btn-primary">Go to wishlist</Link>}>
            Track a part with a target price and we'll let you know when it drops.
          </EmptyState>
        </div>
      )}
      <ul className="mt-6 space-y-2">
        {data?.map((n) => {
          const [Icon, cls] = ICONS[n.kind] || [Bell, "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"];
          return (
            <li key={n.id}>
              <Link
                to={n.link || "#"}
                onClick={() => !n.is_read && markOne(n.id)}
                className={`card flex gap-4 p-4 transition hover:border-indigo-200 dark:hover:border-indigo-500/30 ${n.is_read ? "opacity-70" : "border-indigo-200 dark:border-indigo-500/30 bg-indigo-50/30 dark:bg-indigo-500/10"}`}
              >
                <span className={`h-fit rounded-xl p-2 ${cls}`}><Icon className="h-5 w-5" /></span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="font-semibold">{n.title}</h2>
                    {!n.is_read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-600" aria-label="unread" />}
                  </div>
                  <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-300">{n.body}</p>
                  <p className="mt-1 text-xs text-slate-400">{timeAgo(n.created_at)}</p>
                </div>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
