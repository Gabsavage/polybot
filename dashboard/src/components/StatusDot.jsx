export default function StatusDot({ status, size = "sm" }) {
  const colors = {
    success: "bg-positive",
    failed: "bg-negative",
    running: "bg-warning",
    pending: "bg-text-dim",
  };
  const sizes = { sm: "h-2 w-2", md: "h-3 w-3" };

  return (
    <span
      className={`inline-block rounded-full ${colors[status] || colors.pending} ${sizes[size] || sizes.sm}`}
    />
  );
}
