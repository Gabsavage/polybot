import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { copyToClipboard, truncateAddr } from "../../lib/format";

export default function AddressDisplay({ address, truncate = true, className = "" }) {
  const [copied, setCopied] = useState(false);
  if (!address) return <span className="text-text-secondary">—</span>;
  const display = truncate ? truncateAddr(address) : address;

  async function handleCopy(e) {
    e.stopPropagation();
    if (await copyToClipboard(address)) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <span className={`inline-flex items-center gap-1.5 font-mono text-xs ${className}`}>
      <span>{display}</span>
      <button
        onClick={handleCopy}
        className="text-text-tertiary hover:text-text-primary transition-colors"
        title="Copy address"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
      </button>
    </span>
  );
}
