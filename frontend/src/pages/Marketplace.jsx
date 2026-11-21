import { Link, useSearchParams } from "react-router";
import { MapPin, Plus, Search, ShoppingBag } from "lucide-react";
import { EmptyState, ErrorBox, PageLoader, Pagination, ProductImage } from "../components/ui";
import { CONDITIONS, formatPrice, timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";

export function ListingCard({ listing }) {
  return (
    <Link to={`/marketplace/${listing.id}`} className="card group overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="relative">
        <ProductImage src={listing.cover_image} category={listing.category} alt={listing.title} className="aspect-[4/3] w-full object-cover" />
        {listing.status === "sold" && (
          <span className="absolute left-3 top-3 rounded-full bg-slate-900 px-2 py-0.5 text-xs font-bold text-white">SOLD</span>
        )}
      </div>
      <div className="p-4">
        <h3 className="line-clamp-1 font-semibold group-hover:text-indigo-700 dark:group-hover:text-indigo-300">{listing.title}</h3>
        <div className="mt-1 flex items-center gap-2">
          <span className="tabular text-lg font-bold">{formatPrice(listing.price)}</span>
          {listing.negotiable && <span className="text-xs text-slate-500 dark:text-slate-400">negotiable</span>}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span className="chip">{CONDITIONS[listing.condition]}</span>
          {listing.city && <span className="flex items-center gap-0.5"><MapPin className="h-3 w-3" /> {listing.city}</span>}
          <span>· {timeAgo(listing.created_at)}</span>
        </div>
      </div>
    </Link>
  );
}

export default function Marketplace() {
  const [params, setParams] = useSearchParams();
  const { data: meta } = useApi("/meta");
  const query = Object.fromEntries(params.entries());
  const { data, error, loading } = useApi("/listings", { page_size: 24, ...query });

  const update = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  };

  return (
    <div className="container-page py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Marketplace</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Used and new parts sold by Partify members across Jordan.</p>
        </div>
        <Link to="/marketplace/new" className="btn btn-primary"><Plus className="h-4 w-4" /> Sell an item</Link>
      </div>

      <div className="card mt-6 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <form
          className="relative lg:col-span-2"
          onSubmit={(e) => {
            e.preventDefault();
            update("q", new FormData(e.currentTarget).get("q"));
          }}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input name="q" defaultValue={params.get("q") || ""} placeholder="Search listings…" className="input pl-9" aria-label="Search listings" />
        </form>
        <select className="input" value={params.get("category") || ""} onChange={(e) => update("category", e.target.value)} aria-label="Category">
          <option value="">All categories</option>
          {meta?.listing_categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
        </select>
        <select className="input" value={params.get("condition") || ""} onChange={(e) => update("condition", e.target.value)} aria-label="Condition">
          <option value="">Any condition</option>
          {Object.entries(CONDITIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select className="input" value={params.get("city") || ""} onChange={(e) => update("city", e.target.value)} aria-label="City">
          <option value="">All cities</option>
          {meta?.cities.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="mt-3 flex justify-end">
        <select className="input w-auto py-1.5" value={params.get("sort") || "newest"} onChange={(e) => update("sort", e.target.value)} aria-label="Sort">
          <option value="newest">Newest first</option>
          <option value="price_asc">Lowest price</option>
          <option value="price_desc">Highest price</option>
        </select>
      </div>

      <ErrorBox error={error} className="mt-4" />
      {!data && loading && <PageLoader />}
      {data?.items.length === 0 && (
        <div className="mt-6">
          <EmptyState icon={ShoppingBag} title="No listings yet" action={<Link to="/marketplace/new" className="btn btn-primary">Post the first one</Link>}>
            Upgrading your PC? Sell your old parts to someone who needs them.
          </EmptyState>
        </div>
      )}
      <div className={`mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 ${loading && data ? "opacity-50" : ""}`}>
        {data?.items.map((l) => <ListingCard key={l.id} listing={l} />)}
      </div>
      {data && <Pagination page={data.page} pages={data.pages} onChange={(n) => update("page", n)} />}
    </div>
  );
}
