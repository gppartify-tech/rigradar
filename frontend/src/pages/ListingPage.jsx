import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { CalendarDays, CheckCircle2, Eye, Lock, Mail, MapPin, Pencil, Phone, Tag, Trash2 } from "lucide-react";
import { Avatar, ErrorBox, PageLoader, ProductImage, StoreBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CONDITIONS, formatDate, formatPrice, timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";

export default function ListingPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { data: listing, error, loading, setData } = useApi(`/listings/${id}`);
  const { data: meta } = useApi("/meta");
  const [active, setActive] = useState(0);

  if (loading && !listing) return <PageLoader />;
  if (error) return <div className="container-page py-10"><ErrorBox error={error} /></div>;
  if (!listing) return null;
  const isOwner = user && (user.id === listing.seller.id || user.is_admin);
  const categoryName = meta?.listing_categories.find((c) => c.slug === listing.category)?.name;
  const image = listing.images[active]?.url;
  const saving = listing.product?.best_price ? listing.product.best_price - listing.price : null;

  const setStatus = async (status) => setData(await api(`/listings/${id}`, { method: "PATCH", body: { status } }));
  const remove = async () => {
    if (!window.confirm("Delete this listing for good?")) return;
    await api(`/listings/${id}`, { method: "DELETE" });
    navigate(`/u/${user.username}`);
  };

  return (
    <div className="container-page py-8">
      <Link to="/marketplace" className="text-sm text-slate-500 dark:text-slate-400 hover:text-indigo-700 dark:hover:text-indigo-300">← Marketplace</Link>
      <div className="mt-4 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <div>
          <div className="card overflow-hidden">
            <ProductImage src={image} category={listing.category} alt={listing.title} className="aspect-[4/3] w-full object-contain" />
          </div>
          {listing.images.length > 1 && (
            <div className="mt-3 flex gap-2 overflow-x-auto">
              {listing.images.map((img, i) => (
                <button key={img.id} onClick={() => setActive(i)} className={`shrink-0 overflow-hidden rounded-xl border-2 ${i === active ? "border-indigo-600" : "border-transparent"}`}>
                  <img src={img.url} alt="" className="h-16 w-20 object-cover" />
                </button>
              ))}
            </div>
          )}
          <div className="card mt-6 p-5">
            <h2 className="font-semibold">Description</h2>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-700 dark:text-slate-200" dir="auto">{listing.description || "No description."}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-5">
            {listing.status !== "active" && (
              <span className="mb-3 inline-block rounded-full bg-slate-900 px-2.5 py-0.5 text-xs font-bold uppercase text-white">{listing.status}</span>
            )}
            <h1 className="text-2xl font-bold tracking-tight" dir="auto">{listing.title}</h1>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold">{formatPrice(listing.price)}</span>
              {listing.negotiable && <span className="text-sm text-slate-500 dark:text-slate-400">negotiable</span>}
            </div>
            <div className="mt-4 flex flex-wrap gap-2 text-sm">
              <span className="chip"><Tag className="h-3 w-3" /> {categoryName}</span>
              <span className="chip"><CheckCircle2 className="h-3 w-3" /> {CONDITIONS[listing.condition]}</span>
              {listing.city && <span className="chip"><MapPin className="h-3 w-3" /> {listing.city}</span>}
              <span className="chip"><CalendarDays className="h-3 w-3" /> {timeAgo(listing.created_at)}</span>
              <span className="chip"><Eye className="h-3 w-3" /> {listing.views} views</span>
            </div>
            {isOwner && (
              <div className="mt-5 flex flex-wrap gap-2 border-t border-slate-100 dark:border-slate-800 pt-4">
                <Link to={`/marketplace/${id}/edit`} className="btn btn-secondary btn-sm"><Pencil className="h-4 w-4" /> Edit</Link>
                {listing.status === "active" ? (
                  <button className="btn btn-secondary btn-sm" onClick={() => setStatus("sold")}>Mark as sold</button>
                ) : (
                  <button className="btn btn-secondary btn-sm" onClick={() => setStatus("active")}>Re-activate</button>
                )}
                <button className="btn btn-danger btn-sm" onClick={remove}><Trash2 className="h-4 w-4" /> Delete</button>
              </div>
            )}
          </div>

          <div className="card p-5">
            <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400">Seller</h2>
            <Link to={`/u/${listing.seller.username}`} className="mt-3 flex items-center gap-3 hover:text-indigo-700 dark:hover:text-indigo-300">
              <Avatar user={listing.seller} size="h-12 w-12" />
              <div>
                <div className="font-semibold">{listing.seller.display_name}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">@{listing.seller.username} · member since {formatDate(listing.seller.created_at)}</div>
              </div>
            </Link>
            {listing.seller_contact ? (
              <div className="mt-4 space-y-2 text-sm">
                {listing.seller_contact.phone && (
                  <a href={`tel:${listing.seller_contact.phone}`} className="btn btn-primary w-full"><Phone className="h-4 w-4" /> {listing.seller_contact.phone}</a>
                )}
                <a href={`mailto:${listing.seller_contact.email}?subject=${encodeURIComponent(`Partify: ${listing.title}`)}`} className="btn btn-secondary w-full">
                  <Mail className="h-4 w-4" /> E-mail the seller
                </a>
              </div>
            ) : (
              <Link to={`/login?next=/marketplace/${id}`} className="btn btn-secondary mt-4 w-full"><Lock className="h-4 w-4" /> Log in to see contact details</Link>
            )}
            <p className="mt-3 text-xs text-slate-400">Meet in a public place and test the part before paying.</p>
          </div>

          {listing.product && (
            <Link to={`/product/${listing.product.id}`} className="card block p-5 hover:border-indigo-200 dark:hover:border-indigo-500/30">
              <h2 className="text-sm font-semibold text-slate-500 dark:text-slate-400">Compare with a new one</h2>
              <div className="mt-3 flex items-center gap-3">
                <ProductImage src={listing.product.image_url} category={listing.product.category} className="h-14 w-14 rounded-lg border border-slate-100 dark:border-slate-800" />
                <div className="min-w-0 flex-1">
                  <div className="line-clamp-1 text-sm font-medium">{listing.product.name}</div>
                  <div className="text-sm">
                    New from <span className="font-bold">{formatPrice(listing.product.best_price)}</span> <StoreBadge store={listing.product.best_store} className="text-xs" />
                  </div>
                </div>
              </div>
              {saving > 0 && (
                <p className="mt-3 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-800 dark:text-emerald-200">
                  You save {formatPrice(saving)} ({Math.round((saving / listing.product.best_price) * 100)}%) vs. buying new
                </p>
              )}
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
