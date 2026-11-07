import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { ThemeToggle } from "./components/ui";
import Login from "./pages/Login";
import Settings from "./pages/Settings";

function TopBar() {
  const { user, logout } = useAuth();
  const link = ({ isActive }: { isActive: boolean }) =>
    isActive ? "active" : "";
  return (
    <header className="topbar">
      <div className="brand">
        Shelf Tracker
        <small>Replenishment workload</small>
      </div>
      <nav className="nav">
        <NavLink to="/" end className={link}>
          Settings
        </NavLink>
      </nav>
      <div className="btn-row">
        <ThemeToggle />
        {user && (
          <button className="btn ghost small" onClick={() => logout()}>
            Sign out
          </button>
        )}
      </div>
    </header>
  );
}

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="center">
        <p className="muted">Loading…</p>
      </div>
    );
  }

  if (!user) return <Login />;

  return (
    <div className="app">
      <TopBar />
      <main className="content">
        <Routes>
          <Route path="/" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
