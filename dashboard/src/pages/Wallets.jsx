import useFetch from "../hooks/useFetch";
import DataTable from "../components/DataTable";

export default function Wallets() {
  const { data, loading, refetch } = useFetch("/api/wallets");

  const columns = [
    {
      key: "address", label: "Address", sortable: false,
      render: (v) => <span className="font-mono">{v?.slice(0, 10)}...</span>,
    },
    { key: "notes", label: "Name", sortable: true, render: (v) => v || "—" },
    {
      key: "confidence", label: "Conf", sortable: true,
      render: (v) => (v != null ? Number(v).toFixed(2) : "—"),
    },
    { key: "trades_total", label: "Trades", sortable: true },
    { key: "trades_7d", label: "7d", sortable: true },
    {
      key: "win_rate", label: "Win %", sortable: true,
      render: (v) => {
        if (v == null) return <span className="text-text-dim">—</span>;
        const color =
          v > 55 ? "text-positive" : v < 45 ? "text-negative" : "text-warning";
        return <span className={`font-mono ${color}`}>{v.toFixed(1)}%</span>;
      },
    },
    {
      key: "pnl", label: "P&L", sortable: true,
      render: (v) => {
        if (!v) return <span className="text-text-dim">$0</span>;
        const color = v >= 0 ? "text-positive" : "text-negative";
        return (
          <span className={`font-mono ${color}`}>
            {v >= 0 ? "+" : ""}${Math.abs(v).toFixed(2)}
          </span>
        );
      },
    },
    {
      key: "last_trade", label: "Last Trade", sortable: true,
      render: (v) => v?.slice(0, 10) || "—",
    },
  ];

  function rowClassName(row) {
    if (!row.active) return "opacity-50 line-through";
    if (row.trades_7d === 0) return "border-l-2 border-l-warning";
    return "";
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <h2 className="font-mono text-lg font-bold text-text">
          Wallets Tier A
        </h2>
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
          rowClassName={rowClassName}
        />
      )}
    </div>
  );
}
