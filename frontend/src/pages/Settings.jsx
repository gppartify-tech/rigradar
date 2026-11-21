import { useState } from "react";
import { Camera } from "lucide-react";
import { Avatar, ErrorBox, Field } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/useApi";

function Saved({ show }) {
  return show ? <span className="text-sm font-medium text-emerald-700">Saved ✓</span> : null;
}

export default function Settings() {
  const { user, setUser } = useAuth();
  const { data: meta } = useApi("/meta");
  const [form, setForm] = useState({
    display_name: user.display_name, bio: user.bio || "", city: user.city || "", phone: user.phone || "",
    email_notifications: user.email_notifications,
  });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [status, setStatus] = useState({});
  const [error, setError] = useState(null);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const flash = (key) => {
    setStatus({ [key]: true });
    setTimeout(() => setStatus({}), 2500);
  };

  const saveProfile = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      setUser(await api("/users/me", { method: "PATCH", body: form }));
      flash("profile");
    } catch (err) {
      setError(err);
    }
  };
  const uploadAvatar = async (file) => {
    if (!file) return;
    const data = new FormData();
    data.append("file", file);
    try {
      setUser(await api("/users/me/avatar", { method: "POST", form: data }));
    } catch (err) {
      setError(err);
    }
  };
  const changePassword = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      await api("/users/me/password", { method: "POST", body: pw });
      setPw({ current_password: "", new_password: "" });
      flash("password");
    } catch (err) {
      setError(err);
    }
  };

  return (
    <div className="container-page max-w-3xl py-8">
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Settings</h1>
      <ErrorBox error={error} className="mt-4" />

      <form onSubmit={saveProfile} className="card mt-6 space-y-5 p-6">
        <h2 className="text-lg font-semibold">Public profile</h2>
        <div className="flex items-center gap-4">
          <Avatar user={user} size="h-16 w-16" className="text-xl" />
          <label className="btn btn-secondary btn-sm cursor-pointer">
            <Camera className="h-4 w-4" /> Change photo
            <input type="file" accept="image/*" className="sr-only" onChange={(e) => uploadAvatar(e.target.files[0])} />
          </label>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Display name"><input className="input" required maxLength={60} value={form.display_name} onChange={set("display_name")} /></Field>
          <Field label="City">
            <select className="input" value={form.city} onChange={set("city")}>
              <option value="">—</option>
              {meta?.cities.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </Field>
          <Field label="Phone (shown to logged-in buyers)"><input className="input" maxLength={30} value={form.phone} onChange={set("phone")} placeholder="07X XXX XXXX" /></Field>
        </div>
        <Field label="About you"><textarea className="input min-h-24" maxLength={1000} dir="auto" value={form.bio} onChange={set("bio")} /></Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-indigo-600" checked={form.email_notifications} onChange={set("email_notifications")} />
          E-mail me when a tracked part hits my target price
        </label>
        <div className="flex items-center justify-end gap-3">
          <Saved show={status.profile} />
          <button className="btn btn-primary">Save profile</button>
        </div>
      </form>

      <form onSubmit={changePassword} className="card mt-6 space-y-4 p-6">
        <h2 className="text-lg font-semibold">Password</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Current password"><input type="password" className="input" required value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} autoComplete="current-password" /></Field>
          <Field label="New password" hint="At least 8 characters"><input type="password" className="input" required minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} autoComplete="new-password" /></Field>
        </div>
        <div className="flex items-center justify-end gap-3">
          <Saved show={status.password} />
          <button className="btn btn-secondary">Change password</button>
        </div>
      </form>
    </div>
  );
}
