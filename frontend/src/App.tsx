import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Plan from "./pages/Plan";
import Today from "./pages/Today";
import Clock from "./pages/Clock";

function TopBar() {
  const { user, logout } = useAuth();
  const link = ({ isActive }: { isActive: boolean }) =>
    isActive ? "active" : "";
  return (
    <header className="topbar">
      <nav className="nav">
        <NavLink to="/" end className={link}>
          Plan
        </NavLink>
        <NavLink to="/today" className={link}>
          Today
        </NavLink>
        <NavLink to="/clock" className={link}>
          Clock
        </NavLink>
      </nav>
      <div className="btn-row">
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
          <Route path="/" element={<Plan />} />
          <Route path="/plan" element={<Navigate to="/" replace />} />
          <Route path="/today" element={<Today />} />
          <Route path="/clock" element={<Clock />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
