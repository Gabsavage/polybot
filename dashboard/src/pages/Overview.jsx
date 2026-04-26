import { Link } from "react-router-dom";
import useSWR from "swr";
import { Inbox, ArrowRight } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import KpiCard from "../components/primitives/KpiCard";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import ChartArea from "../components/charts/ChartArea";
import Sparkline from "../components/charts/Sparkline";
import AlertCard from "../components/domain/AlertCard";
import IndexerRow from "../components/domain/IndexerRow";
import HotMarketRow from "../components/domain/HotMarketRow";
import { formatUSD, formatPct } from "../lib/format";
import { pnlColor } from "../lib/colors";

export default function Overview() {
  const { data: perf, error: perfError } = useSWR(urls.performance(30), { refreshInterval: 60_000 });
  const { data: alerts, error: alertsError } = useSWR(urls.alerts({ days: 7 }), { refreshInterval: 60_000 });
  const { data: alerts24 } = useSWR(urls.alerts({ days: 1 }), { refreshInterval: 60_000 });
  const { data: status, error: statusError } = useSWR(urls.status(), { refreshInterval: 30_000 });
  const { data: hotMarkets } = useSWR(urls.hotMarkets(), { refreshInterval: 120_000 });
  const { data: costs } = useSWR(urls.costs());
  const { data: wallets } = useSWR(urls.wallets());

  // Build pnl_series for hero chart from perf.daily
  const pnlSeries = (perf?.daily || []).reduce((acc, d) => {
    const existing = acc.find((x) => x.day === d.day);
    if (existing) existing.cum_pnl = (existing.cum_pnl || 0) + (d.pnl || 0);
    else acc.push({ day: d.day, cum_pnl: d.pnl || 0 });
    return acc;
  }, []);
  // Cumulate
  let runningPnl = 0;
  const pnlChart = pnlSeries.map((p) => {
    runningPnl += p.cum_pnl;
    return { day: p.day, cum_pnl: runningPnl };
  });
  const totalPnl = runningPnl;

  // KPI computations
  const total24 = alerts24?.length ?? 0;
  const totalResolved = perf?.cumulative?.reduce((s, c) => s + (c.alerts || 0), 0) ?? 0;
  const totalCorrect = perf?.cumulative?.reduce((s, c) => s + (c.correct || 0), 0) ?? 0;
  const winRate = totalResolved > 0 ? totalCorrect / totalResolved : null;
  const activeWallets = wallets?.filter((w) => w.active).length ?? 0;
  const totalWallets = wallets?.length ?? 0;

  const recentAlerts = (alerts || []).slice(0, 5);

  return (
    <div className="flex flex-col gap-6">
      {/* Hero */}
      <GlassCard hero className="p-8">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">
              Shadow P&L cumulé
            </div>
            <div className={`text-6xl font-light tracking-tight ${pnlColor(totalPnl)}`}>
              {formatUSD(totalPnl, { signed: true })}
            </div>
            <div className="mt-2 inline-flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full bg-pnl-positive animate-pulse" />
              <span className="text-text-secondary uppercase tracking-wider">Shadow Mode</span>
            </div>
          </div>
        </div>
        <div className="mt-6">
          {perfError ? (
            <ErrorState error={perfError} />
          ) : pnlChart.length === 0 ? (
            <EmptyState icon={Inbox} message="Données P&L insuffisantes" />
          ) : (
            <ChartArea data={pnlChart} height={180} />
          )}
        </div>
      </GlassCard>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Alertes 24h"
          value={total24}
          extra={<Sparkline data={pnlChart.slice(-7)} dataKey="cum_pnl" />}
        />
        <KpiCard label="Win Rate" value={formatPct(winRate)} />
        <KpiCard
          label="Wallets actifs"
          value={`${activeWallets}/${totalWallets}`}
        />
        <KpiCard
          label="Coûts mois"
          value={formatUSD((costs?.llm_cost_estimate || 0) + (costs?.vps_monthly || 0))}
          subtitle={`LLM ${formatUSD(costs?.llm_cost_estimate)} + VPS ${formatUSD(costs?.vps_monthly)}`}
        />
      </div>

      {/* Bottom: Alerts (left) + Indexers (right) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-3 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Dernières alertes</h2>
            <Link to="/alerts" className="text-sm text-accent-orange hover:underline inline-flex items-center gap-1">
              Voir tout <ArrowRight size={14} />
            </Link>
          </div>
          {alertsError ? (
            <ErrorState error={alertsError} />
          ) : !alerts ? (
            <SkeletonList count={5} height={140} />
          ) : recentAlerts.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune alerte récente" />
          ) : (
            recentAlerts.map((a) => <AlertCard key={a.alert_id} alert={a} />)
          )}
        </div>

        <div className="lg:col-span-2 flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Indexers</h2>
          <GlassCard>
            {statusError ? (
              <ErrorState error={statusError} />
            ) : !status ? (
              <SkeletonList count={6} height={32} />
            ) : (
              status.indexers.map((i) => <IndexerRow key={i.name} indexer={i} />)
            )}
          </GlassCard>
        </div>
      </div>

      {/* Hot Markets */}
      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Hot Markets (par score C2)</h2>
        <GlassCard>
          {!hotMarkets ? (
            <SkeletonList count={5} height={56} />
          ) : hotMarkets.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucune alerte C2 sur 7j" />
          ) : (
            hotMarkets.slice(0, 5).map((m) => <HotMarketRow key={m.condition_id} market={m} />)
          )}
        </GlassCard>
      </div>
    </div>
  );
}
