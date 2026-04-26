export default function MobileHeader() {
  return (
    <div className="md:hidden flex items-center gap-3 mb-4 px-1">
      <img src="/logo.png" alt="Polybot" className="w-10 h-10 rounded-lg" />
      <h1 className="font-extrabold text-lg tracking-widest text-text-primary">
        POLYBOT
      </h1>
    </div>
  );
}
