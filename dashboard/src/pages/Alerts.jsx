import { useState } from "react";
import useFetch from "../hooks/useFetch";
import DataTable from "../components/DataTable";

export default function Alerts() {
  const [days, setDays] = useState(7);
  const [component, setComponent] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const params = new URLSearchParams({ days });
  if (component) params.set("component", component);
  const { data, loading, refetch } = useFetch(`/api/alerts?${params}`);

  const columns = [
    {
      key: "emitted_at", label: "Date", sortable: true,
      render: (v) => v?.slice(0, 16).replace("T", " ") || "—",
    },
    { key: "component", label: "Comp", sortable: true },
    {
      key: "market_title", label: "Market", sortable: false,
      render: (v) => (
        <span className="max-w-[200px] truncate inline-block" title={v}>
          {v || "—"}
        </span>
      ),
    },
    { key: "side", label: "Side", sortable: true },
    {
      key: "size_usd", label: "Size", sortable: true,
      render: (v) => (v != null ? `$${Number(v).toFixed(0)}` : "—"),
    },
    {
      key: "price", label: "Price", sortable: true,
      render: (v) => (v != null ? Number(v).toFixed(2) : "—"),
    },
    { key: "score", label: "Score", sortable: true, render: (v) => v ?? "—" },
    {
      key: "alignment_score", label: "Align", sortable: true,
      render: (v) =>
        v === 1 ? "📈" : v === -1 ? "📉" : v === 0 ? "➡️" : "—",
    },
    {
      key: "resolution_outcome", label: "Status", sortable: true,
      render: (v, row) => {
        if (!v || v === "PENDING")
          return <span className="text-text-dim">pending</span>;
        return row.was_direction_correct ? (
          <span className="text-positive">correct</span>
        ) : (
          <span className="text-negative">incorrect</span>
        );
      },
    },
  ];

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">Alerts</h2>
        <div className="flex gap-1 rounded border border-border bg-card text-xs">
          {[null, "C1", "C2"].map((c) => (
            <button
              key={c ?? "all"}
              onClick={() => setComponent(c)}
              className={`px-3 py-1 transition-colors ${
                component === c
                  ? "bg-accent/20 text-accent"
                  : "text-text-dim hover:text-text"
              }`}
            >
              {c ?? "All"}
            </button>
          ))}
        </div>
        <div className="flex gap-1 rounded border border-border bg-card text-xs">
          {[7, 30, 365].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1 transition-colors ${
                days === d
                  ? "bg-accent/20 text-accent"
                  : "text-text-dim hover:text-text"
              }`}
            >
              {d === 365 ? "All" : `${d}d`}
            </button>
          ))}
        </div>
        <button
          onClick={refetch}
          className="ml-auto text-xs text-text-dim hover:text-accent"
        >
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-text-dim">Loading...</p>
      ) : (
        <DataTable
          columns={columns}
          data={data || []}
          onRowClick={(row) =>
            setExpanded(expanded === row.alert_id ? null : row.alert_id)
          }
          rowClassName={(row) =>
            expanded === row.alert_id ? "bg-card/60" : ""
          }
        />
      )}

      {expanded &&
        data &&
        (() => {
          const row = data.find((a) => a.alert_id === expanded);
          if (!row) return null;
          return (
            <div className="mt-2 rounded border border-border bg-card p-4 text-xs">
              <div className="grid gap-2 sm:grid-cols-3">
                <div>
                  <span className="text-text-dim">Alert ID: </span>
                  <span className="font-mono">{row.alert_id}</span>
                </div>
                <div>
                  <span className="text-text-dim">Wallet: </span>
                  <span className="font-mono">
                    {row.wallet_address?.slice(0, 14)}...
                  </span>
                </div>
                <div>
                  <span className="text-text-dim">Market: </span>
                  <span>{row.market_title || row.condition_id}</span>
                </div>
                {row.features_passed && (
                  <div className="sm:col-span-3">
                    <span className="text-text-dim">Features: </span>
                    <span className="font-mono text-accent">
                      {row.features_passed}
                    </span>
                  </div>
                )}
                {row.shadow_pnl_simulated != null && (
                  <div>
                    <span className="text-text-dim">Shadow P&L: </span>
                    <span
                      className={`font-mono ${
                        row.shadow_pnl_simulated >= 0
                          ? "text-positive"
                          : "text-negative"
                      }`}
                    >
                      {row.shadow_pnl_simulated >= 0 ? "+" : ""}$
                      {Math.abs(row.shadow_pnl_simulated).toFixed(2)}
                    </span>
                  </div>
                )}
                {row.price_at_alert != null && (
                  <div>
                    <span className="text-text-dim">Price at alert: </span>
                    <span className="font-mono">
                      {Number(row.price_at_alert).toFixed(2)}
                    </span>
                    {row.price_at_resolution != null && (
                      <span className="font-mono text-text-dim">
                        {" "}
                        → {Number(row.price_at_resolution).toFixed(2)}
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })()}
    </div>
  );
}
