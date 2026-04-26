import GlassCard from "./GlassCard";

export default function KpiCard({ label, value, valueClass = "", subtitle, extra }) {
  return (
    <GlassCard>
      <div className="flex flex-col gap-2">
        <div className="text-xs uppercase tracking-wider text-text-secondary font-medium">
          {label}
        </div>
        <div className={`text-3xl font-bold tracking-tight ${valueClass}`}>
          {value}
        </div>
        {subtitle && (
          <div className="text-xs text-text-secondary">{subtitle}</div>
        )}
        {extra && <div className="mt-2">{extra}</div>}
      </div>
    </GlassCard>
  );
}
