import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useApi } from "../lib/useApi";
import { formatPrice, storeDot } from "../lib/format";
import { Spinner } from "./ui";

// Chart chrome from the validated palette (light mode).
const INK = { secondary: "#52514e", muted: "#898781", grid: "#e1e0d9", axis: "#c3c2b7", surface: "#ffffff" };
const RANGES = [
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 365, label: "1 year" },
  { days: 3650, label: "All" },
];

const dateLabel = (t) => new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const hourLabel = (t) => new Date(t).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
const dateTimeLabel = (t) =>
  new Date(t).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

// Merge every store's points onto one time axis. Prices are step functions:
// a price holds until the next observation, so each series carries its last value forward.
function toRows(series) {
  const times = [...new Set(series.flatMap((s) => s.points.map((p) => new Date(p.t).getTime())))].sort((a, b) => a - b);
  const cursors = series.map(() => ({ i: -1 }));
  return times.map((t) => {
    const row = { t };
    series.forEach((s, idx) => {
      const cur = cursors[idx];
      while (cur.i + 1 < s.points.length && new Date(s.points[cur.i + 1].t).getTime() <= t) cur.i += 1;
      const point = s.points[cur.i];
      row[`s${s.store.id}`] = point ? point.price : null;
      row[`stock${s.store.id}`] = point ? point.in_stock : null;
    });
    return row;
  });
}

function ChartTooltip({ active, payload, label, series }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-lg">
      <div className="mb-1 text-xs text-slate-500">{dateTimeLabel(label)}</div>
      {series.map((s) => {
        const price = row[`s${s.store.id}`];
        if (price === null || price === undefined) return null;
        return (
          <div key={s.store.id} className="flex items-center gap-2 py-0.5">
            <span className="h-0.5 w-3 rounded" style={{ backgroundColor: storeDot(s.store) }} />
            <span className="tabular font-semibold text-slate-900">{formatPrice(price)}</span>
            <span className="text-xs text-slate-500">
              {s.store.name}
              {row[`stock${s.store.id}`] === false ? " · out of stock" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function PriceHistoryChart({ productId }) {
  const [days, setDays] = useState(90);
  const [view, setView] = useState("chart");
  const { data, loading, error } = useApi(`/products/${productId}/history`, { days });
  const series = useMemo(() => (data?.series || []).filter((s) => s.points.some((p) => p.price !== null)), [data]);
  const rows = useMemo(() => toRows(series), [series]);
  const allPoints = useMemo(
    () =>
      series
        .flatMap((s) => s.points.slice(0, s.points.length - 1).map((p) => ({ ...p, store: s.store })))
        .sort((a, b) => new Date(b.t) - new Date(a.t)),
    [series],
  );
  const current = (s) => [...s.points].reverse().find((p) => p.price !== null)?.price;
  // Less than two days of data: label the axis with hours instead of repeating the same date.
  const spanHours = rows.length > 1 ? (rows[rows.length - 1].t - rows[0].t) / 3_600_000 : 0;
  const tickLabel = spanHours < 48 ? hourLabel : dateLabel;

  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Price history</h2>
          <p className="text-sm text-slate-500">Prices recorded at every store check, in JOD.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl bg-slate-100 p-1" role="group" aria-label="Time range">
            {RANGES.map((r) => (
              <button
                key={r.days}
                onClick={() => setDays(r.days)}
                aria-pressed={days === r.days}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold ${days === r.days ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
              >
                {r.label}
              </button>
            ))}
          </div>
          <div className="flex rounded-xl bg-slate-100 p-1" role="group" aria-label="View">
            {["chart", "table"].map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                aria-pressed={view === v}
                className={`rounded-lg px-2.5 py-1 text-xs font-semibold capitalize ${view === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Legend (always shown for 2+ stores) doubles as the direct label: it carries the current price. */}
      {series.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-1">
          {series.map((s) => (
            <li key={s.store.id} className="flex items-center gap-2 text-sm">
              <span className="h-0.5 w-4 rounded" style={{ backgroundColor: storeDot(s.store) }} />
              <span className="text-slate-600">{s.store.name}</span>
              <span className="tabular font-semibold text-slate-900">{formatPrice(current(s))}</span>
              {s.points[s.points.length - 1]?.in_stock === false && <span className="text-xs text-slate-400">out of stock</span>}
            </li>
          ))}
        </ul>
      )}

      <div className={`mt-4 transition-opacity ${loading && data ? "opacity-50" : ""}`}>
        {!data && loading && (
          <div className="flex h-72 items-center justify-center">
            <Spinner />
          </div>
        )}
        {error && <p className="py-10 text-center text-sm text-slate-500">Could not load the price history.</p>}
        {data && series.length === 0 && (
          <p className="py-10 text-center text-sm text-slate-500">No price data in this period yet.</p>
        )}
        {data && series.length > 0 && view === "chart" && (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke={INK.grid} strokeWidth={1} />
                <XAxis
                  dataKey="t"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={tickLabel}
                  tick={{ fill: INK.muted, fontSize: 12 }}
                  axisLine={{ stroke: INK.axis }}
                  tickLine={false}
                  minTickGap={40}
                />
                <YAxis
                  tickFormatter={(v) => v.toLocaleString("en-US")}
                  tick={{ fill: INK.muted, fontSize: 12 }}
                  axisLine={false}
                  tickLine={false}
                  width={56}
                  domain={["auto", "auto"]}
                />
                <Tooltip
                  content={<ChartTooltip series={series} />}
                  cursor={{ stroke: INK.axis, strokeWidth: 1 }}
                  isAnimationActive={false}
                />
                {series.map((s) => (
                  <Line
                    key={s.store.id}
                    dataKey={`s${s.store.id}`}
                    name={s.store.name}
                    type="stepAfter"
                    stroke={storeDot(s.store)}
                    strokeWidth={2}
                    strokeLinejoin="round"
                    strokeLinecap="round"
                    dot={false}
                    activeDot={{ r: 5, stroke: INK.surface, strokeWidth: 2 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {data && series.length > 0 && view === "table" && (
          <div className="max-h-72 overflow-y-auto rounded-xl border border-slate-200">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Store</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2">Stock</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {allPoints.map((p, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2 text-slate-600">{dateTimeLabel(p.t)}</td>
                    <td className="px-3 py-2">{p.store.name}</td>
                    <td className="tabular px-3 py-2 text-right font-semibold">{p.price === null ? "delisted" : formatPrice(p.price)}</td>
                    <td className="px-3 py-2 text-slate-600">{p.in_stock ? "In stock" : "Out of stock"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
