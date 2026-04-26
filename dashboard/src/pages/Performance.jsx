import useSWR from "swr";
import { Inbox, AlertTriangle } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import KpiCard from "../components/primitives/KpiCard";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import ChartLine from "../components/charts/ChartLine";
import ChartDonut from "../components/charts/ChartDonut";
import ChartBar from "../components/charts/ChartBar";
import { formatUSD, formatPct } from "../lib/format";
import { pnlColor } from "../lib/colors";

export default function Performance() {
  const { data, error, isLoading, mutate } = useSWR(urls.performance(30), {
    refreshInterval: 60_000,
  });

  if (error) return <ErrorState error={error} onRetry={() => mutate()} />;
  if (isLoading || !data) return <SkeletonList count={4} height={160} />;

  // Build daily series with C1 + C2 separate columns
  const byDay = {};
  (data.daily || []).forEach((d) => {
    if (!byDay[d.day]) byDay[d.day] = { day: d.day, c1_pnl: 0, c2_pnl: 0 };
    if (d.component === "C1") byDay[d.day].c1_pnl += d.pnl || 0;
    if (d.component === "C2") byDay[d.day].c2_pnl += d.pnl || 0;
  });
  const daysSorted = Object.values(byDay).sort((a, b) => (a.day < b.day ? -1 : 1));
  // Cumulate
  let c1 = 0, c2 = 0;
  const chartData = daysSorted.map((d) => {
    c1 += d.c1_pnl;
    c2 += d.c2_pnl;
    return { day: d.day, c1_pnl: c1, c2_pnl: c2 };
  });

  // KPIs
  const totalAlerts = data.cumulative.reduce((s, c) => s + c.alerts, 0);
  const totalResolved = data.cumulative.reduce((s, c) => s + c.alerts, 0);
  const totalCorrect = data.cumulative.reduce((s, c) => s + c.correct, 0);
  const totalPnl = data.cumulative.reduce((s, c) => s + (c.pnl || 0), 0);
  const winRate = totalResolved > 0 ? totalCorrect / totalResolved : null;
  const avgPnl = totalResolved > 0 ? totalPnl / totalResolved : 0;

  const directionData = [
    { name: "Correct", value: totalCorrect },
    { name: "Incorrect", value: totalResolved - totalCorrect },
  ];

  // alignment distribution (from data.alignment)
  const alignmentData = (data.alignment || []).map((a) => ({
    label: String(a.alignment_score),
    count: a.count,
  }));
  const alignmentColors = (data.alignment || []).map((a) =>
    a.alignment_score > 0 ? "#22c55e" : a.alignment_score < 0 ? "#ef4444" : "#6b7280"
  );

  const insufficient = totalResolved < 30;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl md:text-4xl font-light tracking-tight">Performance</h1>

      {insufficient && (
        <div className="bg-accent-blue/10 border border-accent-blue/30 rounded-card p-4 flex items-start gap-3">
          <AlertTriangle size={18} className="text-accent-blue mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <div className="font-medium text-accent-blue">Échantillon insuffisant</div>
            <div className="text-text-secondary mt-1">
              {totalResolved}/30 minimum. Résultats indicatifs.
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Shadow P&L cumulé (30j)</h2>
        <GlassCard>
          {chartData.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune donnée P&L sur 30j" />
          ) : (
            <ChartLine
              data={chartData}
              xKey="day"
              series={[
                { key: "c1_pnl", color: "#f97316", name: "C1" },
                { key: "c2_pnl", color: "#a855f7", name: "C2" },
              ]}
            />
          )}
        </GlassCard>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Total alertes" value={totalAlerts} />
        <KpiCard label="Win rate" value={formatPct(winRate)} />
        <KpiCard label="Avg P&L / alerte" value={formatUSD(avgPnl, { signed: true })} valueClass={pnlColor(avgPnl)} />
        <KpiCard label="P&L total" value={formatUSD(totalPnl, { signed: true })} valueClass={pnlColor(totalPnl)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Direction correcte</h2>
          <GlassCard>
            {totalResolved === 0 ? (
              <EmptyState icon={Inbox} message="Aucune alerte résolue" />
            ) : (
              <ChartDonut data={directionData} />
            )}
          </GlassCard>
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Alignment distribution</h2>
          <GlassCard>
            {alignmentData.length === 0 ? (
              <EmptyState icon={Inbox} message="Aucune alignment data" />
            ) : (
              <ChartBar data={alignmentData} xKey="count" yKey="label" cellColors={alignmentColors} />
            )}
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
