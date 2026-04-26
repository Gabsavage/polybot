import useFetch from "../hooks/useFetch";
import KpiCard from "../components/KpiCard";
import StatusDot from "../components/StatusDot";
import {
  AreaChart, Area, LineChart, Line, ResponsiveContainer, Tooltip, XAxis,
} from "recharts";

export default function Overview() {
  const { data: status, loading } = useFetch("/api/status", { refreshInterval: 60000 });
  const { data: perf } = useFetch("/api/performance?days=30", { refreshInterval: 60000 });
  const { data: alerts } = useFetch("/api/alerts?days=7", { refreshInterval: 60000 });
  const { data: wallets } = useFetch("/api/wallets", { refreshInterval: 60000 });
  const { data: costs } = useFetch("/api/costs", { refreshInterval: 60000 });

  if (loading) return <p className="text-text-dim">Loading...</p>;

  const allOk = status?.indexers?.every((ix) => ix.status === "success");
  const alerts24h = alerts?.filter(
    (a) => new Date(a.emitted_at) > new Date(Date.now() - 86400000)
  ).length ?? 0;

  const cumul = perf?.cumulative ?? [];
  const totalPnl = cumul.reduce((s, c) => s + (c.pnl || 0), 0);
  const totalResolved = cumul.reduce((s, c) => s + c.resolved, 0);
  const totalCorrect = cumul.reduce((s, c) => s + c.correct, 0);
  const winRate = totalResolved > 0 ? (totalCorrect / totalResolved * 100).toFixed(1) : "—";
  const winColor =
    totalResolved === 0
      ? "accent"
      : parseFloat(winRate) > 55
        ? "positive"
        : parseFloat(winRate) < 45
          ? "negative"
          : "warning";

  const activeWallets = wallets?.filter((w) => w.active && w.trades_7d > 0).length ?? 0;
  const totalWallets = wallets?.length ?? 0;

  // Alerts sparkline
  const alertsByDay = {};
  (alerts || []).forEach((a) => {
    const day = a.emitted_at?.slice(0, 10);
    if (day) alertsByDay[day] = (alertsByDay[day] || 0) + 1;
  });
  const alertSpark = Object.entries(alertsByDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, count]) => ({ day: day.slice(5), count }));

  // P&L sparkline
  let cumPnl = 0;
  const pnlSpark = (perf?.daily || [])
    .reduce((acc, d) => {
      const existing = acc.find((x) => x.day === d.day);
      if (existing) {
        existing.pnl += d.pnl || 0;
      } else {
        acc.push({ day: d.day, pnl: d.pnl || 0 });
      }
      return acc;
    }, [])
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((d) => {
      cumPnl += d.pnl;
      return { day: d.day.slice(5), pnl: parseFloat(cumPnl.toFixed(2)) };
    });

  const pnlSign = totalPnl >= 0 ? "+" : "";
  const pnlColor = totalPnl >= 0 ? "positive" : "negative";

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <h1 className="font-mono text-2xl font-bold text-accent">POLYBOT</h1>
        <StatusDot status={allOk ? "success" : "failed"} size="md" />
        <span className="text-xs text-text-dim">
          {allOk ? "All systems operational" : "Issues detected"}
        </span>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="Alertes 24h" value={alerts24h} color="accent" />
        <KpiCard
          label="Shadow P&L"
          value={`${pnlSign}$${Math.abs(totalPnl).toFixed(2)}`}
          color={pnlColor}
          sub="cumul"
        />
        <KpiCard
          label="Win Rate"
          value={winRate === "—" ? "—" : `${winRate}%`}
          color={winColor}
          sub={totalResolved > 0 ? `${totalCorrect}/${totalResolved}` : null}
        />
        <KpiCard
          label="Wallets Tier A"
          value={`${activeWallets}/${totalWallets}`}
          color="accent"
          sub="actifs cette semaine"
        />
      </div>

      <div className="mb-6 grid gap-3 md:grid-cols-2">
        {alertSpark.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-xs uppercase tracking-wider text-text-dim">
              Alertes / jour (7j)
            </p>
            <ResponsiveContainer width="100%" height={80}>
              <AreaChart data={alertSpark}>
                <defs>
                  <linearGradient id="cyanGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: "#71717a" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#12121a",
                    border: "1px solid #1e1e2e",
                    fontSize: 12,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#06b6d4"
                  fill="url(#cyanGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
        {pnlSpark.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-xs uppercase tracking-wider text-text-dim">
              Shadow P&L cumule (30j)
            </p>
            <ResponsiveContainer width="100%" height={80}>
              <LineChart data={pnlSpark}>
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: "#71717a" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#12121a",
                    border: "1px solid #1e1e2e",
                    fontSize: 12,
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="pnl"
                  stroke={totalPnl >= 0 ? "#22c55e" : "#ef4444"}
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {status?.kill_switches?.length > 0 && (
        <div className="mb-4 rounded-lg border border-negative/50 bg-negative/10 p-3 text-sm text-negative">
          Kill switches actifs: {status.kill_switches.map((ks) => ks.target).join(", ")}
        </div>
      )}

      <div className="mb-6 rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">Indexers</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs uppercase text-text-dim">
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Last Sync</th>
              <th className="px-2 py-1 hidden sm:table-cell">Duration</th>
              <th className="px-2 py-1 hidden sm:table-cell">Count</th>
            </tr>
          </thead>
          <tbody>
            {(status?.indexers || []).map((ix) => (
              <tr key={ix.name} className="border-b border-border/50">
                <td className="px-2 py-1.5 font-mono text-xs">{ix.name}</td>
                <td className="px-2 py-1.5">
                  <StatusDot status={ix.status} />
                </td>
                <td className="px-2 py-1.5 text-xs text-text-dim">
                  {ix.last_synced_at?.slice(0, 19) || "—"}
                </td>
                <td className="px-2 py-1.5 text-xs text-text-dim hidden sm:table-cell">
                  {ix.duration_ms ? `${ix.duration_ms}ms` : "—"}
                </td>
                <td className="px-2 py-1.5 font-mono text-xs hidden sm:table-cell">
                  {ix.ingested_count?.toLocaleString() || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {costs && (
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-2 text-xs uppercase tracking-wider text-text-dim">
            Costs (month)
          </p>
          <div className="flex gap-6 text-sm">
            <span>
              LLM:{" "}
              <span className="font-mono text-accent">
                ${costs.llm_cost_estimate}
              </span>{" "}
              ({costs.llm_calls_month} calls)
            </span>
            <span>
              VPS:{" "}
              <span className="font-mono text-accent">
                ${costs.vps_monthly}/mo
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
