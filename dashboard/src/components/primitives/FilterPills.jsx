export default function FilterPills({ options, value, onChange }) {
  // options: [{ value: "C1", label: "C1" }, ...]
  return (
    <div className="flex gap-1 flex-wrap">
      {options.map((opt) => {
        const active = value === opt.value;
        return (
          <button
            key={opt.value ?? "_all"}
            onClick={() => onChange(opt.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              active
                ? "bg-accent-orange text-bg-primary"
                : "bg-white/[0.05] text-text-secondary hover:bg-white/[0.08] hover:text-text-primary"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
