export default function EmptyState({ icon: Icon, message, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && <Icon size={32} className="text-text-tertiary mb-3" />}
      <div className="text-text-secondary text-sm">{message}</div>
      {subtitle && (
        <div className="text-text-tertiary text-xs mt-1">{subtitle}</div>
      )}
    </div>
  );
}
