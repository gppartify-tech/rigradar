import { useState } from "react";
import { useNavigate } from "react-router";
import { BellRing, Heart } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatPrice } from "../lib/format";
import { ErrorBox, Modal } from "./ui";

// "Track price" button + dialog to set an optional target price.
export default function WishlistButton({ product, wishlist, onChange, compact = false }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(wishlist?.target_price ?? "");
  const [stockAlert, setStockAlert] = useState(wishlist?.notify_back_in_stock ?? true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const tracked = Boolean(wishlist);

  const openDialog = () => {
    if (!user) {
      navigate(`/login?next=/product/${product.id}`);
      return;
    }
    if (!tracked && product.best_price) setTarget(Math.floor(Number(product.best_price) * 0.9));
    setOpen(true);
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = { target_price: target === "" ? null : Number(target), notify_back_in_stock: stockAlert };
      const item = tracked
        ? await api(`/wishlist/${wishlist.id}`, { method: "PATCH", body })
        : await api("/wishlist", { method: "POST", body: { product_id: product.id, ...body } });
      onChange?.({ id: item.id, target_price: item.target_price, notify_back_in_stock: item.notify_back_in_stock });
      setOpen(false);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    setSaving(true);
    try {
      await api(`/wishlist/${wishlist.id}`, { method: "DELETE" });
      onChange?.(null);
      setOpen(false);
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button onClick={openDialog} className={`btn ${tracked ? "btn-secondary border-rose-200 text-rose-600" : "btn-secondary"} ${compact ? "btn-sm" : ""}`}>
        <Heart className={`h-4 w-4 ${tracked ? "fill-rose-500 text-rose-500" : ""}`} />
        {tracked ? (wishlist.target_price ? `Alert at ${formatPrice(wishlist.target_price)}` : "Tracking") : "Track price"}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title={tracked ? "Edit price alert" : "Track this price"}>
        <form onSubmit={save} className="space-y-4">
          <p className="text-sm text-slate-600">
            We check the stores every few hours. Set a target price and we'll notify you (in the app and by e-mail)
            the moment <span className="font-semibold">{product.name}</span> drops to it.
          </p>
          <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm">
            Current best price: <span className="font-semibold">{formatPrice(product.best_price)}</span>
          </div>
          <label className="block">
            <span className="label">Target price (JOD)</span>
            <input
              type="number"
              min="1"
              step="0.5"
              className="input"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="Leave empty to get any 5%+ price drop"
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" className="h-4 w-4 rounded accent-indigo-600" checked={stockAlert} onChange={(e) => setStockAlert(e.target.checked)} />
            Also tell me when it's back in stock
          </label>
          <ErrorBox error={error} />
          <div className="flex flex-wrap justify-end gap-2 pt-2">
            {tracked && (
              <button type="button" className="btn btn-danger mr-auto" onClick={remove} disabled={saving}>
                Stop tracking
              </button>
            )}
            <button type="button" className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
            <button className="btn btn-primary" disabled={saving}>
              <BellRing className="h-4 w-4" /> {tracked ? "Save alert" : "Start tracking"}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
