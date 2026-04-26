export function pnlColor(value) {
  if (value == null) return "text-text-secondary";
  return value > 0 ? "text-pnl-positive" : value < 0 ? "text-pnl-negative" : "text-text-secondary";
}

export function statusColor(status) {
  switch ((status || "").toLowerCase()) {
    case "correct":
    case "success":
    case "active":
      return "text-pnl-positive";
    case "incorrect":
    case "failed":
    case "error":
      return "text-pnl-negative";
    case "running":
    case "pending":
      return "text-accent-blue";
    default:
      return "text-text-secondary";
  }
}

export function sideColor(side) {
  // YES / BUY YES → green ; NO / BUY NO → red
  const s = (side || "").toUpperCase();
  if (s.includes("YES")) return "text-pnl-positive";
  if (s.includes("NO")) return "text-pnl-negative";
  return "text-text-primary";
}

export function componentColor(component) {
  if (component === "C1") return "bg-accent-blue/20 text-accent-blue";
  if (component === "C2") return "bg-accent-violet/20 text-accent-violet";
  return "bg-white/5 text-text-secondary";
}
