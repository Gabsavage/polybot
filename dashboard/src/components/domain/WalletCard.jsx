import { useNavigate } from "react-router-dom";
import { ChevronRight } from "lucide-react";
import GlassCard from "../primitives/GlassCard";
import AddressDisplay from "../primitives/AddressDisplay";
import { formatUSD, formatPct, formatRelative } from "../../lib/format";
import { pnlColor } from "../../lib/colors";

function Stat({ label, value, valueClass = "" }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-text-secondary">{label}</div>
      <div className={`font-medium ${valueClass}`}>{value}</div>
    </div>
  );
}

export default function WalletCard({ wallet }) {
  const navigate = useNavigate();
  const inactive = !wallet.active;
  return (
    <GlassCard
      className={`card-hover cursor-pointer ${inactive ? "opacity-50" : ""}`}
      onClick={() => navigate(`/wallets/${wallet.address}`)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`w-2 h-2 rounded-full ${
                wallet.active ? "bg-pnl-positive" : "bg-pnl-negative"
              }`}
            />
            <span className="font-semibold text-text-primary truncate">
              {wallet.notes || "(sans nom)"}
            </span>
            {inactive && (
              <span className="text-xs px-2 py-0.5 bg-pnl-negative/10 text-pnl-negative rounded">
                DEMOTED
              </span>
            )}
            {wallet.tier === "A" && (
              <span className="text-xs px-2 py-0.5 bg-accent-blue/10 text-accent-blue rounded">
                Tier A
              </span>
            )}
          </div>
          <AddressDisplay address={wallet.address} truncate={false} className="text-text-tertiary" />
          <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Stat label="Trades" value={wallet.trades_total ?? 0} />
            <Stat label="Résolus" value={wallet.resolved ?? 0} />
            <Stat label="Win" value={formatPct(wallet.win_rate != null ? wallet.win_rate / 100 : null)} />
            <Stat
              label="P&L"
              value={formatUSD(wallet.pnl, { signed: true })}
              valueClass={pnlColor(wallet.pnl)}
            />
          </div>
          <div className="mt-2 text-xs text-text-secondary">
            Dernier trade : {formatRelative(wallet.last_trade)}
          </div>
        </div>
        <ChevronRight size={20} className="text-text-tertiary mt-1 flex-shrink-0" />
      </div>
    </GlassCard>
  );
}
