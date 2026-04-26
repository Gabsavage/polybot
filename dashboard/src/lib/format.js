export function formatUSD(value, opts = {}) {
  if (value == null || isNaN(value)) return "—";
  const sign = opts.signed && value > 0 ? "+" : "";
  const fixed = Math.abs(value) >= 1000 ? 0 : 2;
  return `${sign}$${value.toFixed(fixed)}`;
}

export function formatPct(value, decimals = 1) {
  if (value == null || isNaN(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatRelative(isoString) {
  if (!isoString) return "—";
  const d = new Date(isoString);
  const diffSec = (Date.now() - d.getTime()) / 1000;
  if (diffSec < 60) return "à l'instant";
  if (diffSec < 3600) return `il y a ${Math.floor(diffSec / 60)}m`;
  if (diffSec < 86400) return `il y a ${Math.floor(diffSec / 3600)}h`;
  return `il y a ${Math.floor(diffSec / 86400)}j`;
}

export function truncateAddr(addr, chars = 6) {
  if (!addr) return "";
  return `${addr.slice(0, chars)}...${addr.slice(-4)}`;
}

export async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function parseFeaturesSafe(jsonOrStr) {
  if (!jsonOrStr) return [];
  if (typeof jsonOrStr === "string") {
    // Try comma-separated first (legacy format), fall back to JSON
    if (!jsonOrStr.startsWith("[") && !jsonOrStr.startsWith("{")) {
      return jsonOrStr.split(",").map((s) => s.trim()).filter(Boolean);
    }
    try {
      const parsed = JSON.parse(jsonOrStr);
      if (Array.isArray(parsed)) return parsed;
      if (typeof parsed === "object") return Object.keys(parsed);
      return [];
    } catch {
      return [];
    }
  }
  if (Array.isArray(jsonOrStr)) return jsonOrStr;
  return [];
}
