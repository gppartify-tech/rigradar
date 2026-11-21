import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { Radar } from "lucide-react";
import { ErrorBox, Field } from "../components/ui";
import { useAuth } from "../lib/auth";

function AuthCard({ title, subtitle, children }) {
  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <span className="inline-flex rounded-2xl bg-indigo-600 p-3 text-white"><Radar className="h-6 w-6" /></span>
          <h1 className="mt-4 text-2xl font-bold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
        </div>
        <div className="card p-6">{children}</div>
      </div>
    </div>
  );
}

function useNext() {
  const [params] = useSearchParams();
  const next = params.get("next") || "/";
  return next.startsWith("/") && !next.startsWith("//") ? next : "/"; // only local redirects
}

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [form, setForm] = useState({ login: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(form.login, form.password);
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthCard title="Welcome back" subtitle="Log in to see your price alerts and listings.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="E-mail or username"><input className="input" required autoComplete="username" value={form.login} onChange={(e) => setForm({ ...form, login: e.target.value })} /></Field>
        <Field label="Password"><input type="password" className="input" required autoComplete="current-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        <ErrorBox error={error} />
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
        New here? <Link to={`/register?next=${encodeURIComponent(next)}`} className="link">Create an account</Link>
      </p>
    </AuthCard>
  );
}

export function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [form, setForm] = useState({ email: "", username: "", display_name: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, display_name: form.display_name || undefined });
      navigate(next, { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthCard title="Create your account" subtitle="Track prices, get alerts and sell your old parts.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="E-mail"><input type="email" className="input" required autoComplete="email" value={form.email} onChange={set("email")} /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Username" hint="Letters, numbers, _ and ."><input className="input" required minLength={3} maxLength={30} pattern="[A-Za-z0-9_.]+" autoComplete="username" value={form.username} onChange={set("username")} /></Field>
          <Field label="Display name"><input className="input" maxLength={60} value={form.display_name} onChange={set("display_name")} placeholder="Optional" /></Field>
        </div>
        <Field label="Password" hint="At least 8 characters"><input type="password" className="input" required minLength={8} autoComplete="new-password" value={form.password} onChange={set("password")} /></Field>
        <ErrorBox error={error} />
        <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
        Already have an account? <Link to={`/login?next=${encodeURIComponent(next)}`} className="link">Log in</Link>
      </p>
    </AuthCard>
  );
}
