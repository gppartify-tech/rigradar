import { useState } from "react";
import { Link, useParams } from "react-router";
import { CalendarDays, MapPin, Plus, Settings, ShoppingBag } from "lucide-react";
import { Avatar, EmptyState, ErrorBox, PageLoader } from "../components/ui";
import { useAuth } from "../lib/auth";
import { formatDate } from "../lib/format";
import { useApi } from "../lib/useApi";
import { ListingCard } from "./Marketplace";

export default function Profile() {
  const { username } = useParams();
  const { user } = useAuth();
  const [tab, setTab] = useState("active");
  const { data: profile, error, loading } = useApi(`/users/${username}`);
  const isMe = user?.username?.toLowerCase() === username.toLowerCase();
  const { data: listings } = useApi("/listings", { seller: username, status: isMe && tab === "all" ? "all" : tab, page_size: 48 });

  if (loading && !profile) return <PageLoader />;
  if (error) return <div className="container-page py-10"><ErrorBox error={error} /></div>;
  if (!profile) return null;

  const tabs = [
    { key: "active", label: `For sale (${profile.active_listings})` },
    { key: "sold", label: `Sold (${profile.sold_listings})` },
    ...(isMe ? [{ key: "all", label: "All my listings" }] : []),
  ];

  return (
    <div className="container-page py-8">
      <div className="card flex flex-col gap-5 p-6 sm:flex-row sm:items-center">
        <Avatar user={profile} size="h-20 w-20" className="text-2xl" />
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{profile.display_name}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-500 dark:text-slate-400">
            <span>@{profile.username}</span>
            {profile.city && <span className="flex items-center gap-1"><MapPin className="h-4 w-4" /> {profile.city}</span>}
            <span className="flex items-center gap-1"><CalendarDays className="h-4 w-4" /> Member since {formatDate(profile.created_at)}</span>
          </div>
          {profile.bio && <p className="mt-3 max-w-2xl text-sm text-slate-700 dark:text-slate-200" dir="auto">{profile.bio}</p>}
        </div>
        {isMe && (
          <div className="flex gap-2">
            <Link to="/settings" className="btn btn-secondary"><Settings className="h-4 w-4" /> Edit profile</Link>
            <Link to="/marketplace/new" className="btn btn-primary"><Plus className="h-4 w-4" /> Sell</Link>
          </div>
        )}
      </div>

      <div className="mt-6 flex gap-1 border-b border-slate-200 dark:border-slate-800">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold ${tab === t.key ? "border-indigo-600 text-indigo-700 dark:text-indigo-300" : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-100"}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {listings?.items.length === 0 && (
        <div className="mt-6">
          <EmptyState icon={ShoppingBag} title={tab === "sold" ? "Nothing sold yet" : "No listings"}>
            {isMe ? "Post your first item - it only takes a minute." : "Check back later."}
          </EmptyState>
        </div>
      )}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {listings?.items.map((l) => <ListingCard key={l.id} listing={l} />)}
      </div>
    </div>
  );
}
