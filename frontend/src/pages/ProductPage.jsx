import { Link, useParams } from "react-router";
import { ChevronRight, ExternalLink, History, ShoppingBag, Store as StoreIcon, Wrench } from "lucide-react";
import PriceHistoryChart from "../components/PriceHistoryChart";
import { ProductCard } from "../components/ProductCard";
import WishlistButton from "../components/WishlistButton";
import { ErrorBox, PageLoader, ProductImage, StockBadge, StoreBadge } from "../components/ui";
import { useBuild } from "../lib/build";
import { CATEGORY, formatPrice, specLabel, specValue, timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";

function OffersTable({ product }) {
  const best = product.offers.find((o) => o.is_active && o.in_stock) ? product.best_price : null;
  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 px-5 py-4">
        <h2 className="text-lg font-semibold">Prices at each store</h2>
        <span className="text-xs text-slate-500 dark:text-slate-400">Sorted by availability, then price</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="bg-slate-50 dark:bg-slate-800/50 text-left text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <tr>
              <th className="px-5 py-2.5">Store</th>
              <th className="px-3 py-2.5">Availability</th>
              <th className="px-3 py-2.5 text-right">Price</th>
              <th className="px-5 py-2.5 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {product.offers.map((offer) => {
              const isBest = offer.in_stock && offer.is_active && best !== null && offer.price === best;
              return (
                <tr key={offer.id} className={!offer.is_active ? "opacity-50" : isBest ? "bg-emerald-50/50 dark:bg-emerald-500/10" : ""}>
                  <td className="px-5 py-3">
                    <StoreBadge store={offer.store} className="font-semibold" />
                    <div className="mt-0.5 line-clamp-1 max-w-xs text-xs text-slate-500 dark:text-slate-400" title={offer.title}>{offer.title}</div>
                  </td>
                  <td className="px-3 py-3">
                    {offer.is_active ? <StockBadge inStock={offer.in_stock} /> : <span className="chip">No longer listed</span>}
                    <div className="mt-1 text-xs text-slate-400">checked {timeAgo(offer.last_seen_at)}</div>
                  </td>
                  <td className="tabular px-3 py-3 text-right">
                    <div className="text-base font-bold">{formatPrice(offer.price)}</div>
                    {offer.old_price && <div className="text-xs text-slate-400 line-through">{formatPrice(offer.old_price)}</div>}
                    {isBest && <div className="text-xs font-semibold text-emerald-700 dark:text-emerald-300">Best price</div>}
                  </td>
                  <td className="px-5 py-3 text-right">
                    <a href={offer.url} target="_blank" rel="noreferrer noopener" className="btn btn-secondary btn-sm">
                      Visit store <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Specs({ product }) {
  const entries = Object.entries(product.specs || {}).filter(([, v]) => v !== null && v !== undefined);
  if (!entries.length) return null;
  return (
    <section className="card p-5">
      <h2 className="text-lg font-semibold">Specifications</h2>
      <dl className="mt-3 grid gap-x-8 sm:grid-cols-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex justify-between gap-4 border-b border-slate-100 dark:border-slate-800 py-2 text-sm">
            <dt className="text-slate-500 dark:text-slate-400">{specLabel(key)}</dt>
            <dd className="text-right font-medium text-slate-900 dark:text-slate-50">{specValue(key, value)}</dd>
          </div>
        ))}
      </dl>
      {(product.specs?.score || product.specs?.gaming_score) && (
        <p className="mt-3 text-xs text-slate-400">Performance indexes are approximate, relative to the fastest consumer part of each kind.</p>
      )}
    </section>
  );
}

export default function ProductPage() {
  const { id } = useParams();
  const { data: product, error, loading, setData } = useApi(`/products/${id}`);
  const { data: similar } = useApi(`/products/${id}/similar`, { limit: 4 });
  const { build, setPart } = useBuild();

  if (loading && !product) return <PageLoader />;
  if (error) return <div className="container-page py-10"><ErrorBox error={error} /></div>;
  if (!product) return null;
  const category = CATEGORY[product.category];
  const inBuild = build[product.category] === product.id;

  return (
    <div className="container-page py-8">
      <nav className="flex items-center gap-1 text-sm text-slate-500 dark:text-slate-400" aria-label="Breadcrumb">
        <Link to={`/parts/${product.category}`} className="hover:text-indigo-700 dark:hover:text-indigo-300">{category?.name}</Link>
        <ChevronRight className="h-4 w-4" />
        <span className="line-clamp-1 text-slate-700 dark:text-slate-200">{product.name}</span>
      </nav>

      <div className="mt-4 grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="card p-6">
          <ProductImage src={product.image_url} category={product.category} alt={product.name} className="mx-auto aspect-square w-full max-w-sm" />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-medium text-indigo-600 dark:text-indigo-400">{product.brand || category?.singular}</span>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{product.name}</h1>
          <div className="mt-3 flex flex-wrap gap-2">
            <StockBadge inStock={product.in_stock} />
            <span className="chip"><StoreIcon className="h-3 w-3" /> Sold by {product.offer_count} store{product.offer_count === 1 ? "" : "s"}</span>
            {product.lowest_price_ever && (
              <span className="chip"><History className="h-3 w-3" /> Lowest seen {formatPrice(product.lowest_price_ever)}</span>
            )}
          </div>

          <div className="card mt-5 p-5">
            <div className="text-sm text-slate-500 dark:text-slate-400">{product.in_stock ? "Best price today" : "Last known price (out of stock)"}</div>
            <div className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="text-4xl font-extrabold tracking-tight text-slate-900 dark:text-slate-50">{formatPrice(product.best_price)}</span>
              {product.best_store && <StoreBadge store={product.best_store} />}
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              {product.offers[0]?.url && (
                <a href={product.offers[0].url} target="_blank" rel="noreferrer noopener" className="btn btn-primary">
                  Go to {product.offers[0].store.name} <ExternalLink className="h-4 w-4" />
                </a>
              )}
              <WishlistButton product={product} wishlist={product.wishlist} onChange={(w) => setData((p) => ({ ...p, wishlist: w }))} />
              <button className="btn btn-secondary" onClick={() => setPart(product.category, product.id)} disabled={inBuild}>
                <Wrench className="h-4 w-4" /> {inBuild ? "In your build" : "Add to build"}
              </button>
            </div>
            {inBuild && <Link to="/builder" className="link mt-3 inline-block text-sm">Open the PC builder →</Link>}
          </div>

          {product.marketplace_count > 0 && (
            <Link to={`/marketplace?product_id=${product.id}`} className="card mt-4 flex items-center gap-3 p-4 hover:border-indigo-200 dark:hover:border-indigo-500/30">
              <ShoppingBag className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
              <span className="text-sm">
                <span className="font-semibold">{product.marketplace_count} used</span> listing{product.marketplace_count === 1 ? "" : "s"} for this part on the marketplace
              </span>
            </Link>
          )}
        </div>
      </div>

      <div className="mt-6 space-y-6">
        <OffersTable product={product} />
        <PriceHistoryChart productId={product.id} />
        <Specs product={product} />
        {similar?.length > 0 && (
          <section>
            <h2 className="section-title">Similar parts</h2>
            <div className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
              {similar.map((p) => <ProductCard key={p.id} product={p} />)}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
