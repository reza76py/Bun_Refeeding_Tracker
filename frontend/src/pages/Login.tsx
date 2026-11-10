import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { ApiError } from "../api/client";
import { Banner } from "../components/ui";

/** Demo accounts: username == password. */
const ROLES = ["GI", "MNG", "MBR", "admin"] as const;
type DemoRole = (typeof ROLES)[number];

export default function Login() {
  const { login } = useAuth();
  const [role, setRole] = useState<DemoRole | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function pick(r: DemoRole) {
    setRole(r);
    setUsername(r);
    setPassword(r);
    setError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError && typeof err.detail === "string"
          ? err.detail
          : "Sign in failed. Check your username and password."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <div className="card login-card">
        <p className="muted small" style={{ marginTop: 0 }}>
          Demo — username and password are the same.
        </p>

        {!role ? (
          <div className="role-grid">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                className="btn primary role-btn"
                onClick={() => pick(r)}
              >
                {r}
              </button>
            ))}
          </div>
        ) : (
          <form onSubmit={onSubmit}>
            <p className="muted small">
              Username: {role} · Password: {role}
            </p>
            {error && <Banner kind="error">{error}</Banner>}
            <div className="field">
              <label htmlFor="u">Username</label>
              <input
                id="u"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="p">Password</label>
              <input
                id="p"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <button
              className="btn primary"
              style={{ width: "100%" }}
              disabled={busy}
              autoFocus
            >
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <button
              type="button"
              className="btn ghost small"
              style={{ marginTop: "0.6rem" }}
              onClick={() => setRole(null)}
              disabled={busy}
            >
              ← Change role
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
