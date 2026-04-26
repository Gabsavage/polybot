import { statusColor } from "../../lib/colors";

export default function StatusBadge({ status, label }) {
  const color = statusColor(status);
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${color}`}>
      <span className={`w-1.5 h-1.5 rounded-full bg-current`} />
      {label || status}
    </span>
  );
}
