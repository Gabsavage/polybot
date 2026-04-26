import { Outlet } from "react-router-dom";

export default function App() {
  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <main className="p-6">
        <Outlet />
      </main>
    </div>
  );
}
