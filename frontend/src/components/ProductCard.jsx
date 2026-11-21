import { Link } from "react-router";
import { Store as StoreIcon } from "lucide-react";
import { formatPrice, specHighlights } from "../lib/format";
import { ProductImage, StockBadge, StoreBadge } from "./ui";

// Grid card (home page, similar products, deals)
export function ProductCard({ product, badge }) {
  return (
    <Link
      to={`/product/${product.id}`}
      className="card group flex flex-col overflow-hidden transition hover:-translate-y-0.5 hover:border-indigo-200 dark:hover:border-indigo-500/30 hover:shadow-md"
    >
      <div className="relative">
        <ProductImage src={product.image_url} category={product.category} alt={product.name} className="aspect-[4/3] w-full p-4" />
        {badge && <div className="absolute left-3 top-3">{badge}</div>}
      </div>
      <div className="flex flex-1 flex-col border-t border-slate-100 dark:border-slate-800 p-4">
        <h3 className="line-clamp-2 text-sm font-semibold text-slate-900 dark:text-slate-50 group-hover:text-indigo-700 dark:group-hover:text-indigo-300">{product.name}</h3>
        <div className="mt-2 flex flex-wrap gap-1">
          {specHighlights(product).slice(0, 3).map((s) => (
            <span key={s} className="chip">{s}</span>
          ))}
        </div>
        <div className="mt-auto pt-3">
          <div className="tabular text-lg font-bold text-slate-900 dark:text-slate-50">{formatPrice(product.best_price)}</div>
          <div className="mt-1 flex items-center justify-between gap-2">
            <StoreBadge store={product.best_store} className="text-xs" />
            {!product.in_stock && <StockBadge inStock={false} />}
          </div>
        </div>
      </div>
    </Link>
  );
}

// Row layout (browse/search results) - more like a comparison table
export function ProductRow({ product, actions }) {
  return (
    <div className="card flex gap-4 p-3 transition hover:border-indigo-200 dark:hover:border-indigo-500/30 sm:p-4">
      <Link to={`/product/${product.id}`} className="shrink-0">
        <ProductImage
          src={product.image_url}
          category={product.category}
          alt={product.name}
          className="h-20 w-20 rounded-xl border border-slate-100 dark:border-slate-800 p-1 sm:h-24 sm:w-24"
        />
      </Link>
      <div className="flex min-w-0 flex-1 flex-col gap-3 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          <Link to={`/product/${product.id}`} className="line-clamp-2 font-semibold text-slate-900 dark:text-slate-50 hover:text-indigo-700 dark:hover:text-indigo-300">
            {product.name}
          </Link>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {specHighlights(product).map((s) => (
              <span key={s} className="chip">{s}</span>
            ))}
          </div>
        </div>
        <div className="flex items-end justify-between gap-4 sm:w-64 sm:flex-col sm:items-end sm:justify-center">
          <div className="sm:text-right">
            <div className="tabular text-xl font-bold text-slate-900 dark:text-slate-50">{formatPrice(product.best_price)}</div>
            <div className="mt-0.5 flex items-center gap-2 sm:justify-end">
              <StoreBadge store={product.best_store} className="text-xs" />
            </div>
          </div>
          <div className="flex items-center gap-2 sm:justify-end">
            <StockBadge inStock={product.in_stock} />
            <span className="chip" title="Number of stores selling it">
              <StoreIcon className="h-3 w-3" /> {product.offer_count}
            </span>
            {actions}
          </div>
        </div>
      </div>
    </div>
  );
}
