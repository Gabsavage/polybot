import { NavLink } from "react-router-dom";
import { Activity, Zap, Users, TrendingUp, Settings } from "lucide-react";

const NAV = [
  { path: "/", label: "Overview", icon: Activity },
  { path: "/alerts", label: "Alerts", icon: Zap },
  { path: "/wallets", label: "Wallets", icon: Users },
  { path: "/performance", label: "Perf", icon: TrendingUp },
  { path: "/system", label: "System", icon: Settings },
];

export default function MobileNav() {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 flex border-t border-white/[0.06] bg-bg-sidebar/95 backdrop-blur-xl pb-[env(safe-area-inset-bottom)]">
      {NAV.map(({ path, label, icon: Icon }) => (
        <NavLink
          key={path}
          to={path}
          end={path === "/"}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-1 py-2.5 text-[10px] uppercase tracking-wider transition-colors ${
              isActive ? "text-accent-blue" : "text-text-secondary hover:text-text-primary"
            }`
          }
        >
          <Icon size={20} />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
