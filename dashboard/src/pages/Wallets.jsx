import { useState } from "react";
import useSWR from "swr";
import { Inbox } from "lucide-react";
import { urls } from "../api";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import FilterPills from "../components/primitives/FilterPills";
import WalletCard from "../components/domain/WalletCard";

const ACTIVE_OPTIONS = [
  { value: null, label: "Tous" },
  { value: "active", label: "Actifs" },
  { value: "demoted", label: "Démotés" },
];

export default function Wallets() {
  const { data, error, isLoading, mutate } = useSWR(urls.wallets());
  const [activeFilter, setActiveFilter] = useState(null);

  if (error) return <ErrorState error={error} onRetry={() => mutate()} />;
  if (isLoading) return <SkeletonList count={10} height={140} />;
  if (!data?.length) return <EmptyState icon={Inbox} message="Aucun wallet Tier A" />;

  // Sort: active first, then by trades_total desc
  const sorted = [...data].sort((a, b) => {
    if (a.active !== b.active) return a.active ? -1 : 1;
    return (b.trades_total || 0) - (a.trades_total || 0);
  });

  const filtered = sorted.filter((w) => {
    if (activeFilter === "active") return w.active;
    if (activeFilter === "demoted") return !w.active;
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl md:text-4xl font-light tracking-tight">Wallets Tier A</h1>
      <div className="flex items-center gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Statut</div>
          <FilterPills options={ACTIVE_OPTIONS} value={activeFilter} onChange={setActiveFilter} />
        </div>
      </div>
      {filtered.length === 0 ? (
        <EmptyState icon={Inbox} message="Aucun wallet pour ce filtre" />
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((w) => (
            <WalletCard key={w.address} wallet={w} />
          ))}
        </div>
      )}
    </div>
  );
}
