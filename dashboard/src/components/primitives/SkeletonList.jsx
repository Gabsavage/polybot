export default function SkeletonList({ count = 5, height = 96 }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-bg-card-hover animate-pulse rounded-card"
          style={{ height: `${height}px` }}
        />
      ))}
    </div>
  );
}
