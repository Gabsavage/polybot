export default function GlassCard({ hero = false, className = "", children, ...rest }) {
  const base = hero ? "glass-hero p-6" : "glass-card p-6";
  return (
    <div className={`${base} ${className}`} {...rest}>
      {children}
    </div>
  );
}
