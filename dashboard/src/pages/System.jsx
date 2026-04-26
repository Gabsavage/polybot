import useFetch from "../hooks/useFetch";
import StatusDot from "../components/StatusDot";

export default function System() {
  const { data: status, loading, refetch } = useFetch("/api/status");
  const { data: audit } = useFetch("/api/audit?limit=50");

  if (loading) return <p className="text-text-dim">Loading...</p>;

  const icons = {
    kill_switch: "⚙️",
    rate_limit: "⚠️",
    circuit_breaker: "🔧",
    config_change: "💰",
  };

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">System</h2>
        <button
          onClick={refetch}
          className="ml-auto text-xs text-text-dim hover:text-accent"
        >
          ↻ Refresh
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">
            Kill Switches
          </p>
          {(status?.kill_switches || []).length === 0 ? (
            <p className="text-sm text-text-dim">Aucun kill switch actif</p>
          ) : (
            <div className="space-y-2">
              {status.kill_switches.map((ks) => (
                <div
                  key={ks.target}
                  className="flex items-center justify-between rounded border border-negative/30 bg-negative/5 px-3 py-2"
                >
                  <span className="font-mono text-sm text-negative">
                    {ks.target}
                  </span>
                  <span className="text-xs text-text-dim">
                    {ks.reason || "—"}
                  </span>
                  <span className="text-xs text-text-dim">
                    {ks.toggled_at?.slice(0, 19)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">
            Rate Limits
          </p>
          {(status?.rate_limits || []).length === 0 ? (
            <p className="text-sm text-text-dim">Aucun compteur actif</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-text-dim">
                  <th className="px-2 py-1">Component</th>
                  <th className="px-2 py-1">Window</th>
                  <th className="px-2 py-1">Count</th>
                  <th className="px-2 py-1">Since</th>
                </tr>
              </thead>
              <tbody>
                {status.rate_limits.map((rl, i) => (
                  <tr key={i} className="border-t border-border/50">
                    <td className="px-2 py-1 font-mono">{rl.component}</td>
                    <td className="px-2 py-1">{rl.window}</td>
                    <td className="px-2 py-1 font-mono">{rl.count}</td>
                    <td className="px-2 py-1 text-xs text-text-dim">
                      {rl.window_start?.slice(11, 19) || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-lg border border-border bg-card p-4 lg:col-span-2">
          <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">
            Indexers
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {(status?.indexers || []).map((ix) => (
              <div key={ix.name} className="rounded border border-border p-3">
                <div className="mb-2 flex items-center gap-2">
                  <StatusDot status={ix.status} />
                  <span className="font-mono text-sm">{ix.name}</span>
                </div>
                <div className="space-y-0.5 text-xs text-text-dim">
                  <p>Last sync: {ix.last_synced_at?.slice(0, 19) || "—"}</p>
                  <p>
                    Duration: {ix.duration_ms ? `${ix.duration_ms}ms` : "—"}
                  </p>
                  <p>
                    Ingested: {ix.ingested_count?.toLocaleString() || "—"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-border bg-card p-4">
        <p className="mb-3 text-xs uppercase tracking-wider text-text-dim">
          Audit Log
        </p>
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-card">
              <tr className="text-left uppercase text-text-dim">
                <th className="px-2 py-1">Time</th>
                <th className="px-2 py-1">Type</th>
                <th className="px-2 py-1">Target</th>
                <th className="px-2 py-1">Action</th>
                <th className="px-2 py-1 hidden sm:table-cell">Reason</th>
                <th className="px-2 py-1 hidden sm:table-cell">Actor</th>
              </tr>
            </thead>
            <tbody>
              {(audit || []).map((ev) => (
                <tr key={ev.id} className="border-t border-border/50">
                  <td className="px-2 py-1 text-text-dim">
                    {ev.created_at?.slice(11, 19) || "—"}
                  </td>
                  <td className="px-2 py-1">
                    {icons[ev.event_type] || "📋"} {ev.event_type}
                  </td>
                  <td className="px-2 py-1 font-mono">{ev.target}</td>
                  <td className="px-2 py-1">{ev.action}</td>
                  <td className="px-2 py-1 text-text-dim hidden sm:table-cell">
                    {ev.reason || "—"}
                  </td>
                  <td className="px-2 py-1 text-text-dim hidden sm:table-cell">
                    {ev.actor}
                  </td>
                </tr>
              ))}
              {(!audit || audit.length === 0) && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-2 py-4 text-center text-text-dim"
                  >
                    Audit log vide
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
