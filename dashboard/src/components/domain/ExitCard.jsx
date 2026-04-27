import { useNavigate } from "react-router-dom";
import { ExternalLink, LogOut } from "lucide-react";
import GlassCard from "../primitives/GlassCard";
import AddressDisplay from "../primitives/AddressDisplay";
import { formatUSD, formatRelative, formatHeld } from "../../lib/format";

export default function ExitCard({ exit: e }) {
  const navigate = useNavigate();
  const polymarketUrl = e.market_slug
    ? `https://polymarket.com/event/${e.market_slug}`
    : null;
  const pnlSign = e.pnl_pct >= 0 ? "+" : "";
  const pnlColor =
    e.pnl_pct == null
      ? "text-text-secondary"
      : e.pnl_pct >= 0
      ? "text-pnl-positive"
      : "text-pnl-negative";

  return (
    <GlassCard className="card-hover">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-accent-warning/10 text-accent-warning">
            <LogOut size={12} />
            EXIT
          </span>
          <span className="text-xs text-text-secondary">
            {formatRelative(e.created_at)}
          </span>
        </div>
        <span className="text-[10px] font-mono text-text-tertiary">{e.id}</span>
      </div>

      <div className="mt-3 flex items-start justify-between gap-3">
        {polymarketUrl ? (
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-base font-semibold text-text-primary hover:text-accent-blue transition-colors inline-flex items-start gap-1.5"
          >
            {e.market_title || "Marché inconnu"}
            <ExternalLink size={13} className="mt-1 flex-shrink-0 opacity-60" />
          </a>
        ) : (
          <span className="text-base font-semibold text-text-primary">
            {e.market_title || "Marché inconnu"}
          </span>
        )}
        {e.category && (
          <span className="px-2 py-0.5 bg-white/[0.05] text-text-secondary rounded text-[10px] uppercase tracking-wider whitespace-nowrap flex-shrink-0">
            {e.category}
          </span>
        )}
      </div>

      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span className="font-mono text-text-secondary">
          Entry{" "}
          <span className="text-text-primary">{e.entry_price?.toFixed(2)}</span>{" "}
          → Exit{" "}
          <span className="text-text-primary">{e.exit_price?.toFixed(2)}</span>
        </span>
        <span className={`font-semibold ${pnlColor}`}>
          {pnlSign}
          {e.pnl_pct?.toFixed(1)}%
        </span>
        <span className="text-text-secondary">
          Size <span className="text-text-primary">${formatUSD(e.exit_size_usd)}</span>
        </span>
        <span className="text-text-secondary">
          Held <span className="text-text-primary">{formatHeld(e.time_held_h)}</span>
        </span>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs">
        <button
          onClick={() => navigate(`/wallets/${e.wallet_address}`)}
          className="text-text-secondary hover:text-accent-blue transition-colors"
        >
          {e.wallet_name ? (
            <span>
              {e.wallet_name}{" "}
              <AddressDisplay address={e.wallet_address} />
            </span>
          ) : (
            <AddressDisplay address={e.wallet_address} />
          )}
        </button>
        {e.original_alert_id && (
          <span className="font-mono text-text-tertiary">
            Original: {e.original_alert_id}
          </span>
        )}
      </div>
    </GlassCard>
  );
}
