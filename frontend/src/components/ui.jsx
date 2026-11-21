import { useEffect, useState } from "react";
import {
  AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, Info, Keyboard, Laptop, Loader2, Monitor, Package, PcCase, X,
} from "lucide-react";
import { CATEGORY, storeDot } from "../lib/format";

export function Spinner({ className = "" }) {
  return <Loader2 className={`h-5 w-5 animate-spin text-indigo-600 dark:text-indigo-400 ${className}`} aria-label="Loading" />;
}

export function PageLoader() {
  return (
    <div className="flex justify-center py-24">
      <Spinner className="h-8 w-8" />
    </div>
  );
}

export function ErrorBox({ error, className = "" }) {
  if (!error) return null;
  return (
    <div className={`flex items-start gap-2 rounded-xl border border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10 px-4 py-3 text-sm text-rose-800 dark:text-rose-200 ${className}`}>
      <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
      <span>{error.message || String(error)}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon = Info, title, children, action }) {
  return (
    <div className="card flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 rounded-2xl bg-indigo-50 dark:bg-indigo-500/10 p-3 text-indigo-600 dark:text-indigo-400">
        <Icon className="h-7 w-7" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-50">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">{children}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

// Store name with its identity dot (the dot carries the colour, the text stays neutral).
export function StoreBadge({ store, className = "" }) {
  if (!store) return null;
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm text-slate-700 dark:text-slate-200 ${className}`}>
      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: storeDot(store) }} />
      {store.name}
    </span>
  );
}

export function StockBadge({ inStock, compact = false }) {
  if (inStock) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
        <CheckCircle2 className="h-3.5 w-3.5" /> {compact ? "In stock" : "In stock"}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 px-2 py-0.5 text-xs font-semibold text-slate-500 dark:text-slate-400">
      <X className="h-3.5 w-3.5" /> Out of stock
    </span>
  );
}

export function IssueList({ issues }) {
  if (!issues?.length) return null;
  const style = {
    error: ["border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-500/10 text-rose-800 dark:text-rose-200", CircleAlert],
    warning: ["border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 text-amber-900 dark:text-amber-100", AlertTriangle],
    info: ["border-sky-200 dark:border-sky-500/30 bg-sky-50 dark:bg-sky-500/10 text-sky-900 dark:text-sky-100", Info],
  };
  return (
    <ul className="space-y-2">
      {issues.map((issue, i) => {
        const [cls, Icon] = style[issue.level] || style.info;
        return (
          <li key={i} className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-sm ${cls}`}>
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              <span className="font-semibold capitalize">{issue.level}: </span>
              {issue.message}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

// Marketplace ads can also be whole PCs, laptops, monitors...
const EXTRA_ICONS = { pc: PcCase, laptop: Laptop, monitor: Monitor, peripheral: Keyboard, other: Package };

export function ProductImage({ src, category, alt = "", className = "" }) {
  const [failed, setFailed] = useState(false);
  const Icon = CATEGORY[category]?.icon || EXTRA_ICONS[category] || Package;
  if (!src || failed) {
    return (
      <div className={`flex items-center justify-center bg-slate-100 dark:bg-slate-800 text-slate-400 ${className}`}>
        {Icon ? <Icon className="h-1/3 w-1/3" /> : null}
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`bg-white object-contain ${className}`}
    />
  );
}

export function Avatar({ user, size = "h-10 w-10", className = "" }) {
  const initials = (user?.display_name || user?.username || "?").slice(0, 1).toUpperCase();
  if (user?.avatar_url) {
    return <img src={user.avatar_url} alt="" className={`${size} rounded-full object-cover ${className}`} />;
  }
  return (
    <div className={`${size} flex items-center justify-center rounded-full bg-indigo-100 dark:bg-indigo-500/20 font-semibold text-indigo-700 dark:text-indigo-300 ${className}`}>
      {initials}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide = false }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`max-h-[92vh] w-full overflow-y-auto rounded-t-2xl bg-white dark:bg-slate-900 shadow-xl sm:rounded-2xl ${wide ? "sm:max-w-3xl" : "sm:max-w-md"}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-700 dark:hover:text-slate-200" onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Pagination({ page, pages, onChange }) {
  if (!pages || pages <= 1) return null;
  const numbers = [];
  for (let n = Math.max(1, page - 2); n <= Math.min(pages, page + 2); n++) numbers.push(n);
  return (
    <nav className="mt-8 flex items-center justify-center gap-1" aria-label="Pagination">
      <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        <ChevronLeft className="h-4 w-4" /> Prev
      </button>
      {numbers[0] > 1 && <span className="px-2 text-slate-400">…</span>}
      {numbers.map((n) => (
        <button
          key={n}
          onClick={() => onChange(n)}
          aria-current={n === page ? "page" : undefined}
          className={`h-9 min-w-9 rounded-lg px-2 text-sm font-semibold ${n === page ? "bg-indigo-600 text-white" : "text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"}`}
        >
          {n}
        </button>
      ))}
      {numbers[numbers.length - 1] < pages && <span className="px-2 text-slate-400">…</span>}
      <button className="btn btn-ghost btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)}>
        Next <ChevronRight className="h-4 w-4" />
      </button>
    </nav>
  );
}

export function Field({ label, children, hint, error }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-rose-600 dark:text-rose-400">{error}</span>}
    </label>
  );
}
