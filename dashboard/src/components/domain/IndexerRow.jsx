import { formatRelative } from "../../lib/format";
import { statusColor } from "../../lib/colors";

export default function IndexerRow({ indexer }) {
  const dotColor = statusColor(indexer.status).replace("text-", "bg-");
  return (
    <div className="flex items-center justify-between py-2 px-3 row-hover rounded-lg">
      <div className="flex items-center gap-3 min-w-0">
        <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
        <span className="text-sm font-medium truncate">{indexer.name}</span>
      </div>
      <div className="text-xs text-text-secondary whitespace-nowrap">
        {formatRelative(indexer.last_synced_at)}
      </div>
    </div>
  );
}
