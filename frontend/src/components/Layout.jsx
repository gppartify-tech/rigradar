import { Suspense, useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import {
  Bell, Bot, ChevronDown, Heart, LogOut, Menu, Radar, Search, Settings, ShieldCheck, ShoppingBag, User, Wrench, X,
} from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { CATEGORIES, timeAgo } from "../lib/format";
import { useApi } from "../lib/useApi";
import { Avatar, PageLoader, StoreBadge } from "./ui";

const NAV = [
  { to: "/parts/gpu", label: "Parts", match: "/parts" },
  { to: "/builder", label: "PC Builder", icon: Wrench },
  { to: "/assistant", label: "AI Assistant", icon: Bot },
  { to: "/marketplace", label: "Marketplace", icon: ShoppingBag },
];

function SearchBox({ className = "", onDone }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  return (
    <form
      className={`relative ${className}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (!q.trim()) return;
        navigate(`/search?q=${encodeURIComponent(q.trim())}`);
        onDone?.();
      }}
      role="search"
    >
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search parts, e.g. RTX 5070 or Ryzen 7"
        aria-label="Search parts"
        className="w-full rounded-xl border border-slate-700 bg-slate-800 py-2 pl-9 pr-3 text-sm text-white placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-400/30"
      />
    </form>
  );
}

function NotificationBell() {
  const [unread, setUnread] = useState(0);
  const location = useLocation();
  useEffect(() => {
    let alive = true;
    const load = () =>
      api("/notifications/unread-count")
        .then((d) => alive && setUnread(d.unread))
        .catch(() => {});
    load();
    const timer = setInterval(load, 60_000); // poll once a minute
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [location.pathname]);
  return (
    <Link to="/notifications" className="relative rounded-xl p-2 text-slate-300 hover:bg-slate-800 hover:text-white" aria-label={`Notifications (${unread} unread)`}>
      <Bell className="h-5 w-5" />
      {unread > 0 && (
        <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[11px] font-bold text-white">
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </Link>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const navigate = useNavigate();
  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const items = [
    { to: `/u/${user.username}`, label: "My profile & listings", icon: User },
    { to: "/wishlist", label: "Wishlist & alerts", icon: Heart },
    { to: "/notifications", label: "Notifications", icon: Bell },
    { to: "/settings", label: "Settings", icon: Settings },
    ...(user.is_admin ? [{ to: "/admin", label: "Admin dashboard", icon: ShieldCheck }] : []),
  ];
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} className="flex items-center gap-2 rounded-xl p-1 pr-2 hover:bg-slate-800" aria-expanded={open}>
        <Avatar user={user} size="h-8 w-8" />
        <ChevronDown className="h-4 w-4 text-slate-400" />
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-60 overflow-hidden rounded-2xl border border-slate-200 bg-white py-1 text-slate-700 shadow-xl">
          <div className="border-b border-slate-100 px-4 py-3">
            <div className="font-semibold text-slate-900">{user.display_name}</div>
            <div className="text-xs text-slate-500">@{user.username}</div>
          </div>
          {items.map(({ to, label, icon: Icon }) => (
            <Link key={to} to={to} onClick={() => setOpen(false)} className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-slate-50">
              <Icon className="h-4 w-4 text-slate-400" /> {label}
            </Link>
          ))}
          <button
            onClick={() => {
              logout();
              setOpen(false);
              navigate("/");
            }}
            className="flex w-full items-center gap-3 border-t border-slate-100 px-4 py-2 text-left text-sm hover:bg-slate-50"
          >
            <LogOut className="h-4 w-4 text-slate-400" /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

function Navbar() {
  const { user } = useAuth();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);
  const active = (item) => location.pathname.startsWith(item.match || item.to);

  return (
    <header className="sticky top-0 z-30 bg-slate-900 text-white shadow">
      <div className="container-page flex h-16 items-center gap-4">
        <Link to="/" className="flex shrink-0 items-center gap-2">
          <span className="rounded-xl bg-indigo-600 p-1.5">
            <Radar className="h-5 w-5" />
          </span>
          <span className="text-lg font-extrabold tracking-tight">RigRadar</span>
          <span className="hidden rounded-md bg-slate-800 px-1.5 py-0.5 text-[10px] font-bold text-slate-300 sm:inline">JO</span>
        </Link>
        <SearchBox className="hidden max-w-md flex-1 md:block" />
        <nav className="ml-auto hidden items-center gap-1 lg:flex">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={`rounded-xl px-3 py-2 text-sm font-medium ${active(item) ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"}`}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1 lg:ml-2">
          {user ? (
            <>
              <NotificationBell />
              <UserMenu />
            </>
          ) : (
            <div className="hidden items-center gap-2 sm:flex">
              <Link to="/login" className="rounded-xl px-3 py-2 text-sm font-medium text-slate-300 hover:text-white">Log in</Link>
              <Link to="/register" className="btn btn-primary btn-sm">Sign up</Link>
            </div>
          )}
          <button className="rounded-xl p-2 text-slate-300 hover:bg-slate-800 lg:hidden" onClick={() => setMobileOpen((o) => !o)} aria-label="Menu">
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <div className="border-t border-slate-800 lg:hidden">
          <div className="container-page space-y-1 py-3">
            <SearchBox className="mb-2 md:hidden" onDone={() => setMobileOpen(false)} />
            {NAV.map((item) => (
              <Link key={item.to} to={item.to} className="block rounded-xl px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-800">
                {item.label}
              </Link>
            ))}
            {!user && (
              <div className="flex gap-2 pt-2">
                <Link to="/login" className="btn btn-secondary btn-sm flex-1">Log in</Link>
                <Link to="/register" className="btn btn-primary btn-sm flex-1">Sign up</Link>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  );
}

function CategoryBar() {
  const location = useLocation();
  return (
    <div className="border-b border-slate-200 bg-white">
      <div className="container-page flex gap-1 overflow-x-auto py-2">
        {CATEGORIES.map(({ slug, name, icon: Icon }) => {
          const active = location.pathname === `/parts/${slug}`;
          return (
            <Link
              key={slug}
              to={`/parts/${slug}`}
              className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium ${active ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"}`}
            >
              <Icon className="h-4 w-4" /> {name}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function Footer() {
  const { data: stores } = useApi("/stores");
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className="container-page grid gap-8 py-10 md:grid-cols-3">
        <div>
          <div className="flex items-center gap-2 font-extrabold">
            <Radar className="h-5 w-5 text-indigo-600" /> RigRadar
          </div>
          <p className="mt-2 text-sm text-slate-500">
            Compare PC part prices across Jordanian stores, get alerts when prices drop, plan your build with an AI
            assistant and trade used parts with other builders.
          </p>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Stores we track</h3>
          <ul className="mt-3 space-y-2">
            {(stores || []).map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 text-sm">
                <a href={s.base_url} target="_blank" rel="noreferrer" className="hover:underline">
                  <StoreBadge store={s} />
                </a>
                <span className="text-xs text-slate-400">updated {timeAgo(s.last_scraped_at)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="text-sm text-slate-500">
          <h3 className="font-semibold text-slate-900">About the data</h3>
          <p className="mt-3">
            Prices are collected from the stores' public pages every few hours, following each store's robots.txt and at
            a gentle request rate. Always confirm the price on the store's website before buying.
          </p>
        </div>
      </div>
      <div className="border-t border-slate-100 py-4 text-center text-xs text-slate-400">
        RigRadar · Graduation project · Prices in Jordanian Dinar (JOD)
      </div>
    </footer>
  );
}

export default function Layout() {
  const location = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);
  const hideCategories = location.pathname.startsWith("/assistant");
  return (
    <div className="flex min-h-screen flex-col">
      <Navbar />
      {!hideCategories && <CategoryBar />}
      <main className="flex-1">
        <Suspense fallback={<PageLoader />}>
          <Outlet />
        </Suspense>
      </main>
      {!hideCategories && <Footer />}
    </div>
  );
}
