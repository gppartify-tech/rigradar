import { Link } from "react-router";
import { Radar } from "lucide-react";

export default function NotFound() {
  return (
    <div className="container-page flex flex-col items-center py-24 text-center">
      <Radar className="h-12 w-12 text-indigo-500" />
      <h1 className="mt-4 text-3xl font-bold">Page not found</h1>
      <p className="mt-2 text-slate-500 dark:text-slate-400">This page is off our radar.</p>
      <Link to="/" className="btn btn-primary mt-6">Back to the home page</Link>
    </div>
  );
}
