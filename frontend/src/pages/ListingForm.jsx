import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ImagePlus, Link2, Search, X } from "lucide-react";
import { ErrorBox, Field, PageLoader, ProductImage } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CONDITIONS, formatPrice } from "../lib/format";
import { useApi } from "../lib/useApi";

// Optional: link the ad to a catalog product, so buyers can compare with the new price.
function ProductLink({ category, product, onChange }) {
  const [q, setQ] = useState("");
  const isPart = ["cpu", "gpu", "motherboard", "ram", "storage", "psu", "case", "cooler"].includes(category);
  const { data } = useApi(q.length >= 2 && isPart ? "/products" : null, { q, category, page_size: 6 });
  if (!isPart) return null;
  if (product) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-slate-200 dark:border-slate-800 p-3">
        <ProductImage src={product.image_url} category={product.category} className="h-10 w-10 rounded-lg" />
        <div className="min-w-0 flex-1 text-sm">
          <div className="line-clamp-1 font-medium">{product.name}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">New from {formatPrice(product.best_price)}</div>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => onChange(null)} aria-label="Unlink product"><X className="h-4 w-4" /></button>
      </div>
    );
  }
  return (
    <div>
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input className="input pl-9" placeholder="Type the model, e.g. RTX 3060" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {data?.items?.length > 0 && (
        <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800 rounded-xl border border-slate-200 dark:border-slate-800">
          {data.items.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => { onChange(p); setQ(""); }} className="flex w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800">
                <ProductImage src={p.image_url} category={p.category} className="h-8 w-8 rounded" />
                <span className="line-clamp-1 flex-1">{p.name}</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">{formatPrice(p.best_price)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ListingForm() {
  const { id } = useParams();
  const editing = Boolean(id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: meta } = useApi("/meta");
  const { data: existing } = useApi(editing ? `/listings/${id}` : null);
  const [form, setForm] = useState({ title: "", description: "", category: "gpu", condition: "good", price: "", negotiable: true, city: user?.city || "" });
  const [product, setProduct] = useState(null);
  const [images, setImages] = useState([]); // already uploaded (edit mode)
  const [files, setFiles] = useState([]); // new files to upload
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!existing) return;
    setForm({
      title: existing.title, description: existing.description, category: existing.category, condition: existing.condition,
      price: existing.price, negotiable: existing.negotiable, city: existing.city || "",
    });
    setProduct(existing.product);
    setImages(existing.images);
  }, [existing]);

  if (editing && !existing) return <PageLoader />;
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const maxImages = 6;

  const addFiles = (list) => {
    const picked = [...list].filter((f) => f.type.startsWith("image/")).slice(0, maxImages - images.length - files.length);
    setFiles((cur) => [...cur, ...picked.map((file) => ({ file, url: URL.createObjectURL(file) }))]);
  };
  const removeExisting = async (imageId) => {
    const updated = await api(`/listings/${id}/images/${imageId}`, { method: "DELETE" });
    setImages(updated.images);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = { ...form, price: Number(form.price), city: form.city || null, product_id: product?.id ?? null };
      const saved = editing
        ? await api(`/listings/${id}`, { method: "PATCH", body })
        : await api("/listings", { method: "POST", body });
      for (const { file } of files) {
        const data = new FormData();
        data.append("file", file);
        await api(`/listings/${saved.id}/images`, { method: "POST", form: data });
      }
      navigate(`/marketplace/${saved.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-page max-w-3xl py-8">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{editing ? "Edit listing" : "Sell an item"}</h1>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Good photos and an honest description sell faster.</p>
      <form onSubmit={submit} className="card mt-6 space-y-5 p-6">
        <Field label="Title">
          <input className="input" required minLength={5} maxLength={150} value={form.title} onChange={set("title")} placeholder="e.g. MSI RTX 3060 Ventus 12GB - 1 year old" />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Category">
            <select className="input" value={form.category} onChange={set("category")}>
              {meta?.listing_categories.map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </select>
          </Field>
          <Field label="Condition">
            <select className="input" value={form.condition} onChange={set("condition")}>
              {Object.entries(CONDITIONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <Field label="Price (JOD)">
            <input className="input" type="number" min="1" step="0.5" required value={form.price} onChange={set("price")} />
          </Field>
          <Field label="City">
            <select className="input" value={form.city} onChange={set("city")}>
              <option value="">Select a city</option>
              {meta?.cities.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={form.negotiable} onChange={set("negotiable")} /> Price is negotiable
        </label>
        <Field label="Description" hint="Age, warranty, reason for selling, what's included in the box…">
          <textarea className="input min-h-32" maxLength={5000} dir="auto" value={form.description} onChange={set("description")} />
        </Field>
        <div>
          <span className="label flex items-center gap-1"><Link2 className="h-4 w-4" /> Link to the catalog (optional)</span>
          <ProductLink category={form.category} product={product} onChange={setProduct} />
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">Buyers will see how much they save compared to the new price.</p>
        </div>
        <div>
          <span className="label">Photos ({images.length + files.length}/{maxImages})</span>
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-6">
            {images.map((img) => (
              <div key={img.id} className="relative">
                <img src={img.url} alt="" className="aspect-square w-full rounded-xl object-cover" />
                <button type="button" onClick={() => removeExisting(img.id)} className="absolute -right-2 -top-2 rounded-full bg-white dark:bg-slate-900 p-1 shadow" aria-label="Remove photo"><X className="h-3.5 w-3.5" /></button>
              </div>
            ))}
            {files.map((f, i) => (
              <div key={f.url} className="relative">
                <img src={f.url} alt="" className="aspect-square w-full rounded-xl object-cover" />
                <button type="button" onClick={() => setFiles((cur) => cur.filter((_, j) => j !== i))} className="absolute -right-2 -top-2 rounded-full bg-white dark:bg-slate-900 p-1 shadow" aria-label="Remove photo"><X className="h-3.5 w-3.5" /></button>
              </div>
            ))}
            {images.length + files.length < maxImages && (
              <label className="flex aspect-square cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-700 text-slate-400 hover:border-indigo-400 hover:text-indigo-600 dark:hover:text-indigo-400">
                <ImagePlus className="h-6 w-6" />
                <span className="mt-1 text-xs">Add</span>
                <input type="file" accept="image/*" multiple className="sr-only" onChange={(e) => addFiles(e.target.files)} />
              </label>
            )}
          </div>
        </div>
        <ErrorBox error={error} />
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-ghost" onClick={() => navigate(-1)}>Cancel</button>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Saving…" : editing ? "Save changes" : "Publish listing"}</button>
        </div>
      </form>
    </div>
  );
}
