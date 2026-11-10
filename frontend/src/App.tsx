import type { ReactNode } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import type { Page } from "./api/types";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Plan from "./pages/Plan";
import Today from "./pages/Today";
import Clock from "./pages/Clock";
import Settings from "./pages/Settings";

/** Which role gets the report button on which page (not admin). */
const REPORT_ROLE: Partial<Record<Page, string>> = {
  plan: "gi",
  today: "mng",
  clock: "mbr",
};

/** Every page, in nav order. Which ones a user sees comes from /api/auth/me. */
const PAGES: Record<Page, { path: string; label: string; element: ReactNode }> = {
  plan: { path: "/plan", label: "GI", element: <Plan /> },
  today: { path: "/today", label: "MNG", element: <Today /> },
  clock: { path: "/clock", label: "MBR", element: <Clock /> },
  settings: { path: "/settings", label: "Settings", element: <Settings /> },
};

function TopBar({ pages }: { pages: Page[] }) {
  const { logout } = useAuth();
  const link = ({ isActive }: { isActive: boolean }) =>
    isActive ? "active" : "";
  return (
    <header className="topbar">
      <nav className="nav">
        {pages.map((p) => (
          <NavLink key={p} to={PAGES[p].path} className={link}>
            {PAGES[p].label}
          </NavLink>
        ))}
      </nav>
      <div className="btn-row">
        <button className="btn ghost small" onClick={() => logout()}>
          Sign out
        </button>
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

  const pages = (user.pages ?? []).filter((p) => p in PAGES);
  // Not allowed / unknown paths go to the user's first page.
  const home = pages.length ? PAGES[pages[0]].path : null;

  return (
    <div className="app">
      <TopBar pages={pages} />
      <main className="content">
        {home ? (
          <Routes>
            {pages.map((p) => (
              <Route
                key={p}
                path={PAGES[p].path}
                element={
                  <>
                    {user.role && REPORT_ROLE[p] === user.role && (
                      <div className="btn-row graph-toggle">
                        <button className="btn small" onClick={() => window.print()}>
                          {PAGES[p].label} report
                        </button>
                      </div>
                    )}
                    {PAGES[p].element}
                    <p className="page-name">{PAGES[p].label}</p>
                  </>
                }
              />
            ))}
            <Route path="*" element={<Navigate to={home} replace />} />
          </Routes>
        ) : (
          <p className="muted">This account has no pages.</p>
        )}
      </main>
    </div>
  );
}
