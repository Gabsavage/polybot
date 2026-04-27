import useSWR from "swr";
import { useParams, Link } from "react-router-dom";
import { ExternalLink, ArrowLeft, Inbox } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import KpiCard from "../components/primitives/KpiCard";
import AddressDisplay from "../components/primitives/AddressDisplay";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import StatusBadge from "../components/primitives/StatusBadge";
import ChartArea from "../components/charts/ChartArea";
import { formatUSD, formatPct, formatRelative } from "../lib/format";
import { pnlColor, sideColor } from "../lib/colors";

function tradeStatus(t) {
  if (!t.resolution_outcome) return "pending";
  return t.was_direction_correct ? "correct" : "incorrect";
}

export default function WalletDetail() {
  const { address } = useParams();
  const { data, error, isLoading, mutate } = useSWR(urls.walletDetail(address));
  const { data: trades } = useSWR(urls.walletTrades(address, 100));

  if (error) {
    if (error.status === 404) {
      return (
        <div className="flex flex-col items-center justify-center py-16 gap-4">
          <h1 className="text-xl text-text-primary">Wallet non suivi</h1>
          <Link to="/wallets" className="text-accent-blue hover:underline inline-flex items-center gap-1">
            <ArrowLeft size={14} /> Retour aux wallets
          </Link>
        </div>
      );
    }
    return <ErrorState error={error} onRetry={() => mutate()} />;
  }
  if (isLoading || !data) return <SkeletonList count={4} height={120} />;

  const polymarketUrl = `https://polymarket.com/profile/${address}`;

  return (
    <div className="flex flex-col gap-6">
      <Link to="/wallets" className="text-sm text-text-secondary hover:text-accent-blue inline-flex items-center gap-1 w-fit">
        <ArrowLeft size={14} /> Retour
      </Link>

      <GlassCard>
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-light tracking-tight">{data.name || "(sans nom)"}</h1>
            <div className="mt-2">
              <AddressDisplay address={data.address} truncate={false} />
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-0.5 bg-accent-blue/10 text-accent-blue rounded">
                Tier {data.tier}
              </span>
              {data.tier_a_confidence != null && (
                <span className="px-2 py-0.5 bg-white/[0.05] rounded text-text-secondary">
                  conf: {data.tier_a_confidence.toFixed(2)}
                </span>
              )}
              {!data.active && (
                <span className="px-2 py-0.5 bg-pnl-negative/10 text-pnl-negative rounded">DEMOTED</span>
              )}
            </div>
          </div>
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 rounded-lg text-sm font-medium transition-colors"
          >
            Voir sur Polymarket <ExternalLink size={14} />
          </a>
        </div>
      </GlassCard>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KpiCard label="Trades" value={data.trades_total ?? 0} />
        <KpiCard label="Résolus" value={data.resolved ?? 0} />
        <KpiCard label="Win Rate" value={formatPct(data.win_rate)} />
        <KpiCard
          label="Shadow P&L"
          value={formatUSD(data.pnl, { signed: true })}
          valueClass={pnlColor(data.pnl)}
        />
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">P&L cumulé (90j)</h2>
        <GlassCard>
          {!data.pnl_series?.length ? (
            <EmptyState icon={Inbox} message="Aucune alerte résolue" />
          ) : (
            <ChartArea data={data.pnl_series} xKey="day" yKey="cum_pnl" />
          )}
        </GlassCard>
      </div>

      {data.cex_funding && (
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">CEX funding</h2>
          <GlassCard>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Source</div>
                <div className="font-medium">{data.cex_funding.cex_source}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Confidence</div>
                <div className="font-medium">{data.cex_funding.confidence?.toFixed(2)}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Method</div>
                <div className="font-medium font-mono text-xs">{data.cex_funding.method}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Deposit</div>
                <AddressDisplay address={data.cex_funding.deposit_address} />
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      {data.cluster && (
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Cluster</h2>
          <GlassCard>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Cluster ID</div>
                <div className="font-medium font-mono text-xs">{data.cluster.cluster_id}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Size</div>
                <div className="font-medium">{data.cluster.size}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">CEX</div>
                <div className="font-medium">{data.cluster.cex_source || "—"}</div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-text-secondary">Funded by</div>
                <AddressDisplay address={data.cluster.funded_by} />
              </div>
            </div>
          </GlassCard>
        </div>
      )}

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Trades récents</h2>
        <GlassCard className="overflow-x-auto">
          {!trades ? (
            <SkeletonList count={5} height={32} />
          ) : trades.length === 0 ? (
            <EmptyState icon={Inbox} message="Aucun trade enregistré" />
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-text-secondary">
                  <th className="pb-2">Date</th>
                  <th className="pb-2">Marché</th>
                  <th className="pb-2">Direction</th>
                  <th className="pb-2 text-right">Size</th>
                  <th className="pb-2 text-right">Prix</th>
                  <th className="pb-2 text-right">Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.transaction_hash} className="border-t border-white/[0.04]">
                    <td className="py-2 text-text-secondary whitespace-nowrap">
                      {formatRelative(t.timestamp_ts)}
                    </td>
                    <td className="py-2 max-w-xs truncate">{t.market_title || "—"}</td>
                    <td className={`py-2 font-medium ${sideColor(t.outcome)}`}>
                      {t.side} {t.outcome || "—"}
                    </td>
                    <td className="py-2 text-right">{formatUSD(t.size_usd)}</td>
                    <td className="py-2 text-right">{t.price?.toFixed(2) ?? "—"}</td>
                    <td className="py-2 text-right">
                      <StatusBadge status={tradeStatus(t)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
