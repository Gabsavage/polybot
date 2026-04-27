import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink, ChevronDown } from "lucide-react";
import GlassCard from "../primitives/GlassCard";
import StatusBadge from "../primitives/StatusBadge";
import AddressDisplay from "../primitives/AddressDisplay";
import { formatUSD, formatRelative, parseFeaturesSafe } from "../../lib/format";
import { sideColor, componentColor } from "../../lib/colors";

function alertStatus(alert) {
  if (!alert.resolution_outcome || alert.resolution_outcome === "PENDING") return "pending";
  return alert.was_direction_correct ? "correct" : "incorrect";
}

export default function AlertCard({ alert }) {
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();
  const status = alertStatus(alert);
  const features = parseFeaturesSafe(alert.features_passed);
  const polymarketUrl = alert.market_slug
    ? `https://polymarket.com/event/${alert.market_slug}`
    : null;

  return (
    <GlassCard className="card-hover cursor-pointer" onClick={() => setExpanded((v) => !v)}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-semibold ${componentColor(alert.component)}`}>
            {alert.component}
          </span>
          <span className="text-xs text-text-secondary">{formatRelative(alert.emitted_at)}</span>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          <ChevronDown
            size={16}
            className={`text-text-tertiary transition-transform ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </div>
      <div className="mt-3 text-base font-semibold text-text-primary">
        {alert.market_title || "Marché inconnu"}
      </div>
      <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span className={`font-semibold ${sideColor(alert.outcome)}`}>
          {alert.side || "BUY"} {alert.outcome || "—"} @ {alert.price?.toFixed(2)}
        </span>
        <span className="text-text-secondary">
          ${formatUSD(alert.size_usd)} <span className="text-text-tertiary">(wallet)</span>
        </span>
        {alert.score != null && (
          <span className="text-text-secondary">
            Score: <span className="text-text-primary font-medium">{alert.score}/8</span>
          </span>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between text-xs">
        <button
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/wallets/${alert.wallet_address}`);
          }}
          className="text-text-secondary hover:text-accent-blue transition-colors"
        >
          <AddressDisplay address={alert.wallet_address} />
        </button>
        {polymarketUrl && (
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="inline-flex items-center gap-1 text-text-secondary hover:text-accent-blue transition-colors"
          >
            Polymarket <ExternalLink size={11} />
          </a>
        )}
      </div>
      {expanded && (
        <div className="mt-4 pt-4 border-t border-white/[0.06] text-sm space-y-2">
          {alert.alignment_score != null && (
            <div className="flex justify-between">
              <span className="text-text-secondary">Alignment :</span>
              <span className="font-mono">{alert.alignment_score}</span>
            </div>
          )}
          {features.length > 0 && (
            <div>
              <div className="text-text-secondary mb-1">Features :</div>
              <div className="flex flex-wrap gap-1">
                {features.map((f) => (
                  <span
                    key={f}
                    className="px-2 py-0.5 bg-accent-violet/10 text-accent-violet rounded text-xs"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}
          {alert.shadow_pnl_simulated != null && (
            <div className="flex justify-between">
              <span className="text-text-secondary">Shadow P&L :</span>
              <span>{formatUSD(alert.shadow_pnl_simulated, { signed: true })}</span>
            </div>
          )}
          <div className="text-xs text-text-tertiary font-mono">
            ID : {alert.alert_id}
          </div>
        </div>
      )}
    </GlassCard>
  );
}
