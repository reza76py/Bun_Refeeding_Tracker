import { useCallback, useEffect, useState, type ReactNode } from "react";
import { api } from "../api/client";
import type { RunningCage } from "../api/types";
import { aisleName, durDays } from "../lib/format";
import { useRefetchOnFocus } from "../lib/useRefetchOnFocus";
import { Banner, Loading } from "./ui";

/** Every unfinished cage as a horizontal bar of time since it was created
 * on Plan; the longest-unfinished cage is full width. Ticks every second.
 * (Finished = ended on Clock or 100% on Today; the backend leaves those out.) */
export function GraphView() {
  const [rows, setRows] = useState<RunningCage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      setRows(await api.graphRunning());
      setError(null);
    } catch {
      setError("Could not load.");
    }
  }, []);

  useEffect(() => {
    load();
    const poll = window.setInterval(load, 30_000); // pick up new/finished cages
    const tick = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => {
      window.clearInterval(poll);
      window.clearInterval(tick);
    };
  }, [load]);
  useRefetchOnFocus(load);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!rows) return <Loading what="Loading" />;
  if (rows.length === 0) return <p className="muted">No active cages.</p>;

  const bars = rows.map((r) => ({
    ...r,
    secs: Math.max(0, (now - Date.parse(r.created_at)) / 1000),
  }));
  const longest = Math.max(1, ...bars.map((b) => b.secs));

  return (
    <div className="graph">
      {bars.map((b) => (
        <div key={b.cage_id} className="graph-row">
          <div className="graph-label">
            <strong>{b.code}</strong>
            <span className="muted small"> · {aisleName(b.aisle_label)}</span>
          </div>
          <div className="graph-track">
            <div
              className="graph-bar"
              style={{ width: `${Math.max(2, (b.secs / longest) * 100)}%` }}
            />
          </div>
          <div className="graph-time">{durDays(b.secs)}</div>
        </div>
      ))}
    </div>
  );
}

/** Wraps a page with a "Graph" button; Graph shows only the GraphView, and
 * "Table" goes back to the page. Local state only. */
export function WithGraph({ children }: { children: ReactNode }) {
  const [graph, setGraph] = useState(false);
  return (
    <>
      <div className="btn-row graph-toggle">
        <button
          className={graph ? "btn ghost small" : "btn small"}
          onClick={() => setGraph((g) => !g)}
        >
          {graph ? "← Table" : "Graph"}
        </button>
      </div>
      {graph ? (
        <div className="card">
          <GraphView />
        </div>
      ) : (
        children
      )}
    </>
  );
}
