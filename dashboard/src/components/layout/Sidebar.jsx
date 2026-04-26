import { NavLink } from "react-router-dom";
import { Activity, Zap, Users, TrendingUp, Settings } from "lucide-react";

const NAV = [
  { path: "/", label: "Overview", icon: Activity },
  { path: "/alerts", label: "Alerts", icon: Zap },
  { path: "/wallets", label: "Wallets", icon: Users },
  { path: "/performance", label: "Performance", icon: TrendingUp },
  { path: "/system", label: "System", icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-60 lg:w-60 md:flex-col glass-card my-3 ml-3 mr-0 py-6 px-4 sticky top-3 h-[calc(100vh-1.5rem)]">
      <div className="flex items-center gap-3 mb-10 px-1">
        <img src="/logo.png" alt="Polybot" className="w-14 h-14 rounded-xl" />
        <h1 className="font-extrabold text-xl tracking-widest text-text-primary">
          POLYBOT
        </h1>
      </div>
      <nav className="flex flex-col gap-1">
        {NAV.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-accent-blue/10 text-accent-blue border-l-[3px] border-accent-blue pl-[9px]"
                  : "text-text-secondary hover:bg-white/[0.05] hover:text-text-primary"
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
