export default function KpiCard({ label, value, sub, color }) {
  const colorClass = {
    positive: "text-positive",
    negative: "text-negative",
    accent: "text-accent",
    warning: "text-warning",
  }[color] || "text-text";

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wider text-text-dim">{label}</p>
      <p className={`mt-1 font-mono text-2xl font-bold ${colorClass}`}>{value}</p>
      {sub && <p className="mt-0.5 text-xs text-text-dim">{sub}</p>}
    </div>
  );
}
