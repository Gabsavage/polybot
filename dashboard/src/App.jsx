import { Routes, Route, NavLink } from "react-router-dom";
import Overview from "./pages/Overview";
import Alerts from "./pages/Alerts";
import Wallets from "./pages/Wallets";
import Performance from "./pages/Performance";
import System from "./pages/System";

const NAV = [
  { path: "/", label: "Overview", icon: "\u25c9" },
  { path: "/alerts", label: "Alerts", icon: "\u26a1" },
  { path: "/wallets", label: "Wallets", icon: "\u25c6" },
  { path: "/performance", label: "Perf", icon: "\u25b3" },
  { path: "/system", label: "System", icon: "\u2699" },
];

function Sidebar() {
  return (
    <nav className="hidden md:flex md:w-48 flex-col border-r border-border bg-card p-4">
      <h1 className="mb-8 font-mono text-xl font-bold text-accent">POLYBOT</h1>
      {NAV.map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          end={n.path === "/"}
          className={({ isActive }) =>
            `mb-1 rounded px-3 py-2 text-sm transition-colors ${
              isActive ? "bg-accent/10 text-accent" : "text-text-dim hover:text-text"
            }`
          }
        >
          <span className="mr-2">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

function MobileNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 flex border-t border-border bg-card md:hidden">
      {NAV.map((n) => (
        <NavLink
          key={n.path}
          to={n.path}
          end={n.path === "/"}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center py-2 text-xs ${
              isActive ? "text-accent" : "text-text-dim"
            }`
          }
        >
          <span className="text-lg">{n.icon}</span>
          {n.label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function App() {
  return (
    <div className="flex h-screen bg-bg">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-4 pb-20 md:p-6 md:pb-6">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/wallets" element={<Wallets />} />
          <Route path="/performance" element={<Performance />} />
          <Route path="/system" element={<System />} />
        </Routes>
      </main>
      <MobileNav />
    </div>
  );
}
