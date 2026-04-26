import { ExternalLink } from "lucide-react";
import { parseFeaturesSafe } from "../../lib/format";

export default function HotMarketRow({ market }) {
  const features = parseFeaturesSafe(market.features_last);
  const polymarketUrl = market.slug ? `https://polymarket.com/event/${market.slug}` : null;
  return (
    <div className="flex items-center justify-between gap-4 py-3 px-3 row-hover rounded-lg">
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-text-primary truncate">
          {market.title}
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {features.map((f) => (
            <span
              key={f}
              className="px-1.5 py-0.5 bg-accent-violet/10 text-accent-violet rounded text-[10px]"
            >
              {f}
            </span>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-sm font-mono">
          <span className="text-text-primary font-bold">{market.c2_score_max}</span>
          <span className="text-text-tertiary">/8</span>
        </span>
        {polymarketUrl && (
          <a
            href={polymarketUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-text-tertiary hover:text-accent-orange transition-colors"
          >
            <ExternalLink size={14} />
          </a>
        )}
      </div>
    </div>
  );
}
