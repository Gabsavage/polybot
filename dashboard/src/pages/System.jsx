import useSWR from "swr";
import { Inbox, Power, Activity, Shield } from "lucide-react";
import { urls } from "../api";
import GlassCard from "../components/primitives/GlassCard";
import EmptyState from "../components/primitives/EmptyState";
import ErrorState from "../components/primitives/ErrorState";
import SkeletonList from "../components/primitives/SkeletonList";
import { formatRelative } from "../lib/format";
import { statusColor } from "../lib/colors";

function eventIcon(eventType) {
  if (eventType === "kill_switch") return Power;
  if (eventType === "rate_limit") return Shield;
  return Activity;
}

export default function System() {
  const { data: status, error: statusError, mutate: mutateStatus } = useSWR(urls.status(), {
    refreshInterval: 30_000,
  });
  const { data: audit, error: auditError } = useSWR(urls.audit(50));

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-bold">System</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Indexers</h2>
          {statusError ? (
            <ErrorState error={statusError} onRetry={() => mutateStatus()} />
          ) : !status ? (
            <SkeletonList count={6} height={56} />
          ) : (
            <GlassCard>
              {status.indexers.map((i) => (
                <div key={i.name} className="py-2 px-3 row-hover rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full ${statusColor(i.status).replace("text-", "bg-")}`}
                      />
                      <span className="font-medium">{i.name}</span>
                    </div>
                    <span className="text-xs text-text-secondary">
                      {formatRelative(i.last_synced_at)}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-text-tertiary flex gap-4">
                    <span>Status: {i.status || "—"}</span>
                    <span>Duration: {i.duration_ms ?? "—"}ms</span>
                    <span>Ingested: {i.ingested_count ?? 0}</span>
                  </div>
                </div>
              ))}
            </GlassCard>
          )}
        </div>

        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold">Kill switches</h2>
          {!status ? (
            <SkeletonList count={4} height={48} />
          ) : status.kill_switches.length === 0 ? (
            <GlassCard>
              <EmptyState icon={Power} message="Aucun kill switch actif" />
            </GlassCard>
          ) : (
            <GlassCard>
              {status.kill_switches.map((k) => (
                <div key={k.target} className="flex items-center justify-between py-2 px-3 row-hover rounded-lg">
                  <div>
                    <div className="font-medium">{k.target}</div>
                    {k.reason && <div className="text-xs text-text-secondary">{k.reason}</div>}
                  </div>
                  <span className="px-2 py-0.5 bg-pnl-negative/10 text-pnl-negative rounded text-xs font-medium">
                    ENABLED
                  </span>
                </div>
              ))}
            </GlassCard>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Rate limits</h2>
        {!status ? (
          <SkeletonList count={3} height={48} />
        ) : status.rate_limits.length === 0 ? (
          <GlassCard>
            <EmptyState icon={Shield} message="Aucun rate limit actif" />
          </GlassCard>
        ) : (
          <GlassCard>
            {status.rate_limits.map((r) => (
              <div key={`${r.component}-${r.window}`} className="py-2 px-3 row-hover rounded-lg">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{r.component}</span>
                  <span className="text-text-secondary">{r.window}</span>
                  <span className="font-mono">{r.count}</span>
                </div>
              </div>
            ))}
          </GlassCard>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <h2 className="text-xl font-semibold">Audit log</h2>
        {auditError ? (
          <ErrorState error={auditError} />
        ) : !audit ? (
          <SkeletonList count={6} height={64} />
        ) : audit.length === 0 ? (
          <EmptyState icon={Inbox} message="Aucun événement enregistré" />
        ) : (
          <div className="flex flex-col gap-2">
            {audit.map((a) => {
              const Icon = eventIcon(a.event_type);
              return (
                <GlassCard key={a.id} className="!p-4">
                  <div className="flex items-start gap-3">
                    <Icon size={16} className="text-accent-orange mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium">
                          {a.event_type} · {a.target} · {a.action}
                        </span>
                        <span className="text-xs text-text-secondary">
                          {formatRelative(a.created_at)}
                        </span>
                      </div>
                      {a.reason && (
                        <div className="text-xs text-text-secondary mt-1">{a.reason}</div>
                      )}
                      {a.actor && (
                        <div className="text-xs text-text-tertiary mt-0.5">par {a.actor}</div>
                      )}
                    </div>
                  </div>
                </GlassCard>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
