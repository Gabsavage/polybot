import { Outlet } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
import MobileNav from "./components/layout/MobileNav";
import MobileHeader from "./components/layout/MobileHeader";

export default function App() {
  return (
    <div className="flex min-h-screen bg-bg-primary text-text-primary">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-4 md:p-6 md:pl-3 pb-24 md:pb-6">
        <MobileHeader />
        <TopBar />
        <Outlet />
      </main>
      <MobileNav />
    </div>
  );
}
