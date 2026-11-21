import { Link, useNavigate } from "react-router";
import { CheckCircle2, CircleAlert, Wrench } from "lucide-react";
import { setBuildParts } from "../lib/build";
import { CATEGORY, formatPrice } from "../lib/format";
import { ProductImage, StoreBadge } from "./ui";

// Compact card for a recommended build (used by the assistant).
export default function BuildSummary({ build }) {
  const navigate = useNavigate();
  const openInBuilder = () => {
    setBuildParts(Object.fromEntries(build.parts.map((p) => [p.category, p.product.id])));
    navigate("/builder");
  };
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 px-4 py-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Suggested build</div>
          <div className="tabular text-lg font-bold">
            {formatPrice(build.total_price)} <span className="text-sm font-normal text-slate-500 dark:text-slate-400">/ budget {formatPrice(build.budget)}</span>
          </div>
        </div>
        {build.compatible ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5" /> Compatible
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 dark:bg-rose-500/10 px-2.5 py-1 text-xs font-semibold text-rose-700 dark:text-rose-300">
            <CircleAlert className="h-3.5 w-3.5" /> Check issues
          </span>
        )}
      </div>
      <ul className="divide-y divide-slate-100 dark:divide-slate-800">
        {build.parts.map((part) => (
          <li key={part.category} className="flex items-center gap-3 px-4 py-2.5">
            <ProductImage src={part.product.image_url} category={part.category} className="h-10 w-10 rounded-lg border border-slate-100 dark:border-slate-800" />
            <div className="min-w-0 flex-1">
              <div className="text-xs text-slate-500 dark:text-slate-400">{CATEGORY[part.category]?.singular}</div>
              <Link to={`/product/${part.product.id}`} className="line-clamp-1 text-sm font-medium hover:text-indigo-700 dark:hover:text-indigo-300">
                {part.product.name}
              </Link>
            </div>
            <div className="text-right">
              <div className="tabular text-sm font-semibold">{formatPrice(part.price)}</div>
              <StoreBadge store={part.product.best_store} className="text-xs" />
            </div>
          </li>
        ))}
      </ul>
      <div className="flex justify-end border-t border-slate-100 dark:border-slate-800 px-4 py-3">
        <button className="btn btn-primary btn-sm" onClick={openInBuilder}>
          <Wrench className="h-4 w-4" /> Open in PC Builder
        </button>
      </div>
    </div>
  );
}
