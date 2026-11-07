import { useState, type FormEvent } from "react";
import { useAuth } from "../auth";
import { ApiError } from "../api/client";
import { Banner, ThemeToggle } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
        <div className="row-between" style={{ marginBottom: "0.5rem" }}>
          <h1 style={{ margin: 0 }}>Shelf Tracker</h1>
          <ThemeToggle />
        </div>
        <p className="muted small">
          Personal replenishment workload tool. Sign in to continue.
        </p>
        {error && <Banner kind="error">{error}</Banner>}
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="u">Username</label>
            <input
              id="u"
              autoFocus
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
          <button className="btn primary" style={{ width: "100%" }} disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
