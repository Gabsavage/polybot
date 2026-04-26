import { useState } from "react";
import useFetch from "../hooks/useFetch";
import KpiCard from "../components/KpiCard";
import {
  LineChart, Line, BarChart, Bar, ResponsiveContainer,
  Tooltip, XAxis, YAxis, Legend, CartesianGrid,
} from "recharts";

export default function Performance() {
  const [days, setDays] = useState(30);
  const { data, loading, refetch } = useFetch(`/api/performance?days=${days}`);

  if (loading) return <p className="text-text-dim">Loading...</p>;
  if (!data) return null;

  const { daily, cumulative, alignment } = data;

  const totalAlerts = cumulative.reduce((s, c) => s + c.total, 0);
  const totalResolved = cumulative.reduce((s, c) => s + c.resolved, 0);
  const totalCorrect = cumulative.reduce((s, c) => s + c.correct, 0);
  const totalPnl = cumulative.reduce((s, c) => s + (c.pnl || 0), 0);
  const pending = totalAlerts - totalResolved;
  const correctPct =
    totalResolved > 0
      ? ((totalCorrect / totalResolved) * 100).toFixed(1)
      : "—";
  const incorrectPct =
    totalResolved > 0
      ? (((totalResolved - totalCorrect) / totalResolved) * 100).toFixed(1)
      : "—";

  const dayMap = {};
  daily.forEach((d) => {
    if (!dayMap[d.day]) dayMap[d.day] = { day: d.day, C1: 0, C2: 0 };
    if (d.component === "C1") dayMap[d.day].C1 = d.pnl || 0;
    if (d.component === "C2") dayMap[d.day].C2 = d.pnl || 0;
  });
  let cumC1 = 0,
    cumC2 = 0;
  const pnlSeries = Object.values(dayMap)
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((d) => {
      cumC1 += d.C1;
      cumC2 += d.C2;
      return {
        day: d.day.slice(5),
        C1: parseFloat(cumC1.toFixed(2)),
        C2: parseFloat(cumC2.toFixed(2)),
        Total: parseFloat((cumC1 + cumC2).toFixed(2)),
      };
    });

  const alignMap = {};
  (alignment || []).forEach((a) => {
    alignMap[a.score] = a.count;
  });
  const alignData = [
    { label: "Contrariant", value: alignMap[-1] || 0 },
    { label: "Neutre", value: alignMap[0] || 0 },
    { label: "Suit", value: alignMap[1] || 0 },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">Performance</h2>
        <div className="flex gap-1 rounded border border-border bg-card text-xs">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 transition-colors ${
                days === d
                  ? "bg-accent/20 text-accent"
                  : "text-text-dim hover:text-text"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
        <button
          onClick={refetch}
          className="ml-auto text-xs text-text-dim hover:text-accent"
        >
          ↻ Refresh
        </button>
      </div>

      {totalResolved < 30 && (
        <div className="mb-4 rounded border border-warning/50 bg-warning/10 p-3 text-sm text-warning">
          Echantillon &lt; 30 alertes resolues — donnees insuffisantes pour
          conclure
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <KpiCard label="Total alertes" value={totalAlerts} color="accent" />
        <KpiCard label="Resolues" value={totalResolved} color="accent" />
        <KpiCard label="Pending" value={pending} color="warning" />
        <KpiCard
          label="Correct %"
          value={correctPct === "—" ? "—" : `${correctPct}%`}
          color={parseFloat(correctPct) > 55 ? "positive" : "warning"}
        />
        <KpiCard
          label="Incorrect %"
          value={incorrectPct === "—" ? "—" : `${incorrectPct}%`}
          color="negative"
        />
      </div>

      {pnlSeries.length > 0 && (
        <div className="mb-6 rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">
            Shadow P&L cumule ({days}j)
          </p>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={pnlSeries}>
              <CartesianGrid stroke="#1e1e2e" />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 10, fill: "#71717a" }}
              />
              <YAxis tick={{ fontSize: 10, fill: "#71717a" }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#12121a",
                  border: "1px solid #1e1e2e",
                  fontSize: 12,
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="Total"
                stroke="#e4e4e7"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="C1"
                stroke="#06b6d4"
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="C2"
                stroke="#f59e0b"
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {alignment && alignment.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">
            Alignment C2
          </p>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={alignData}>
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "#71717a" }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#12121a",
                  border: "1px solid #1e1e2e",
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" fill="#06b6d4" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
