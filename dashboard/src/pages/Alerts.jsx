import useSWR from "swr";
import { useSearchParams } from "react-router-dom";
import { Inbox } from "lucide-react";
import { urls } from "../api";
import FilterPills from "../components/primitives/FilterPills";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import AlertCard from "../components/domain/AlertCard";

const COMPONENT_OPTIONS = [
  { value: null, label: "Tous" },
  { value: "C1", label: "C1" },
  { value: "C2", label: "C2" },
];
const PERIOD_OPTIONS = [
  { value: "1", label: "24h" },
  { value: "7", label: "7j" },
  { value: "30", label: "30j" },
  { value: "365", label: "All" },
];
const STATUS_OPTIONS = [
  { value: null, label: "Tous" },
  { value: "pending", label: "Pending" },
  { value: "correct", label: "Correct" },
  { value: "incorrect", label: "Incorrect" },
];

function alertStatus(alert) {
  if (!alert.resolution_outcome || alert.resolution_outcome === "PENDING") return "pending";
  return alert.was_direction_correct ? "correct" : "incorrect";
}

export default function Alerts() {
  const [params, setParams] = useSearchParams();
  const component = params.get("component");
  const days = params.get("days") || "7";
  const status = params.get("status");
  const category = params.get("category");

  const { data, error, isLoading, mutate } = useSWR(
    urls.alerts({ days: parseInt(days), component }),
    { refreshInterval: 60_000 }
  );

  function setParam(key, value) {
    const next = new URLSearchParams(params);
    if (value == null) next.delete(key);
    else next.set(key, value);
    setParams(next);
  }

  const categoryOptions = [
    { value: null, label: "Toutes" },
    ...Array.from(new Set((data || []).map((a) => a.category).filter(Boolean)))
      .sort()
      .map((c) => ({ value: c, label: c })),
  ];

  const filtered = (data || []).filter((a) => {
    if (status && alertStatus(a) !== status) return false;
    if (category && a.category !== category) return false;
    return true;
  });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl md:text-4xl font-light tracking-tight">Alertes</h1>

      <div className="flex flex-col md:flex-row md:items-center gap-4 flex-wrap">
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Composant</div>
          <FilterPills options={COMPONENT_OPTIONS} value={component} onChange={(v) => setParam("component", v)} />
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Période</div>
          <FilterPills options={PERIOD_OPTIONS} value={days} onChange={(v) => setParam("days", v)} />
        </div>
        <div>
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Status</div>
          <FilterPills options={STATUS_OPTIONS} value={status} onChange={(v) => setParam("status", v)} />
        </div>
        {categoryOptions.length > 1 && (
          <div>
            <div className="text-xs uppercase tracking-wider text-text-secondary mb-1">Catégorie</div>
            <FilterPills options={categoryOptions} value={category} onChange={(v) => setParam("category", v)} />
          </div>
        )}
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : isLoading ? (
        <SkeletonList count={8} height={140} />
      ) : !filtered?.length ? (
        <EmptyState icon={Inbox} message="Aucune alerte sur ces critères" />
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map((a) => (
            <AlertCard key={a.alert_id} alert={a} />
          ))}
        </div>
      )}
    </div>
  );
}
