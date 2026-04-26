import useSWR from "swr";
import { RefreshCw } from "lucide-react";
import { urls } from "../../api";
import { formatUSD, formatPct } from "../../lib/format";
import { pnlColor } from "../../lib/colors";

function Pill({ label, value, valueClass = "" }) {
  return (
    <div className="flex items-center gap-2 bg-white/[0.05] rounded-full px-3 py-1 text-xs whitespace-nowrap">
      <span className="text-text-secondary uppercase tracking-wider">{label}</span>
      <span className={`font-semibold ${valueClass}`}>{value}</span>
    </div>
  );
}

export default function TopBar() {
  const { data: status, mutate: mutateStatus } = useSWR(urls.status(), {
    refreshInterval: 30_000,
  });
  const { data: perf, mutate: mutatePerf } = useSWR(urls.performance(30), {
    refreshInterval: 60_000,
  });
  const { data: alerts, mutate: mutateAlerts } = useSWR(urls.alerts({ days: 1 }), {
    refreshInterval: 60_000,
  });

  // Compute Shadow P&L total
  const totalPnl = perf?.cumulative?.reduce(
    (sum, c) => sum + (c.pnl || 0), 0
  );

  // Win rate over all resolved
  const totalResolved = perf?.cumulative?.reduce(
    (sum, c) => sum + (c.alerts || 0), 0
  );
  const totalCorrect = perf?.cumulative?.reduce(
    (sum, c) => sum + (c.correct || 0), 0
  );
  const winRate = totalResolved > 0 ? totalCorrect / totalResolved : null;

  // Indexers status
  const indexers = status?.indexers || [];
  const okCount = indexers.filter((i) => i.status === "success").length;
  const total = indexers.length;
  const indexerStatus =
    total === 0
      ? "—"
      : okCount === total
      ? `${okCount}/${total} ✓`
      : okCount === total - 1
      ? `${okCount}/${total} ⚠`
      : `${okCount}/${total} ✗`;
  const indexerClass =
    okCount === total
      ? "text-pnl-positive"
      : okCount >= total - 1
      ? "text-accent-orange"
      : "text-pnl-negative";

  function refreshAll() {
    mutateStatus();
    mutatePerf();
    mutateAlerts();
  }

  return (
    <div className="flex items-center gap-2 mb-6 overflow-x-auto">
      <Pill
        label="Shadow P&L"
        value={formatUSD(totalPnl, { signed: true })}
        valueClass={pnlColor(totalPnl)}
      />
      <Pill label="Alertes 24h" value={alerts?.length ?? "—"} />
      <Pill label="Win Rate" value={formatPct(winRate)} />
      <Pill label="Indexers" value={indexerStatus} valueClass={indexerClass} />
      <button
        onClick={refreshAll}
        className="ml-auto p-2 rounded-lg hover:bg-white/[0.05] text-text-secondary hover:text-text-primary transition-colors"
        title="Refresh all"
      >
        <RefreshCw size={16} />
      </button>
    </div>
  );
}
