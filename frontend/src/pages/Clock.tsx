import { useCallback, useEffect, useState } from "react";
import { api, clockExportUrl } from "../api/client";
import type { ClockSummary } from "../api/types";
import { Banner, Loading } from "../components/ui";
import { aisleName, durDays, stamp } from "../lib/format";
import { useRefetchOnFocus } from "../lib/useRefetchOnFocus";

/** Per cage: Start when refeeding it begins, End when it finishes. Sessions
 * can run over several days and every one is kept as history. */
export default function Clock() {
  const [data, setData] = useState<ClockSummary | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await api.clockSummary());
      setError(null);
    } catch {
      setError("Could not load.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);
  useRefetchOnFocus(load);

  async function act(cageId: number, fn: (id: number) => Promise<unknown>) {
    setBusy(cageId);
    setError(null);
    try {
      await fn(cageId);
    } catch {
      setError("Could not save.");
    }
    await load();
    setBusy(null);
  }

  if (!data) {
    return (
      <div className="card">
        {error ? <Banner kind="error">{error}</Banner> : <Loading what="Loading" />}
      </div>
    );
  }

  return (
    <div className="card">
      {error && <Banner kind="error">{error}</Banner>}

      {data.aisles.map((aisle, i) => (
        <div key={aisle.aisle_id} style={{ marginTop: i ? "1.5rem" : 0 }}>
          <h3 style={{ margin: 0 }}>{aisleName(aisle.label)}</h3>
          {aisle.cages.map((c) => {
            const off = busy === c.cage_id;
            const last = c.last_session;
            return (
              <div key={c.cage_id} className="clock-row">
                <strong>{c.code}</strong>
                <div className="btn-row">
                  {c.open_session ? (
                    <>
                      <span>Running since {stamp(c.open_session.start_at)}</span>
                      <button
                        className="btn primary clock-btn"
                        onClick={() => act(c.cage_id, api.clockEnd)}
                        disabled={off}
                      >
                        End
                      </button>
                      <button
                        className="btn ghost small"
                        onClick={() => {
                          if (window.confirm(`Cancel the running session for ${c.code}?`))
                            act(c.cage_id, api.clockCancel);
                        }}
                        disabled={off}
                      >
                        Cancel
                      </button>
                    </>
                  ) : last ? (
                    <span>
                      Start {stamp(last.start_at)} → End {stamp(last.end_at)} ·{" "}
                      <strong>{durDays(last.duration_seconds)}</strong>
                    </span>
                  ) : (
                    <button
                      className="btn primary clock-btn"
                      onClick={() => act(c.cage_id, api.clockStart)}
                      disabled={off}
                    >
                      Start
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}

      {data.aisles.length > 0 && (
        <>
          <div className="divider" />
          <a className="small muted" href={clockExportUrl} download>
            Export CSV
          </a>
        </>
      )}
    </div>
  );
}
