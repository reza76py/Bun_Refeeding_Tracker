import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { FeedCage, FeedSummary } from "../api/types";
import { Banner, Loading } from "../components/ui";
import {
  aisleName,
  nowBrisbaneHM,
  shiftLocal,
  todayBrisbane,
} from "../lib/format";
import { useRefetchOnFocus } from "../lib/useRefetchOnFocus";

/** Per cage: tick = fully fed (100%), or type how much %. Totals are weighted
 * by each cage's planned time. */
export default function Today() {
  const [date, setDate] = useState(todayBrisbane);
  const [data, setData] = useState<FeedSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!date) return;
    try {
      setData(await api.feedSummary(date));
      setError(null);
    } catch {
      setError("Could not load.");
    }
  }, [date]);

  useEffect(() => {
    setData(null);
    load();
  }, [load]);
  useRefetchOnFocus(load);

  async function save(cageId: number, percent: number) {
    // Show the change straight away; the reload brings the new totals.
    setData((d) =>
      d && {
        ...d,
        aisles: d.aisles.map((a) => ({
          ...a,
          cages: a.cages.map((c) =>
            c.cage_id === cageId ? { ...c, percent } : c
          ),
        })),
      }
    );
    try {
      await api.setFeed({ date, cage_id: cageId, percent });
    } catch {
      setError("Could not save.");
    }
    await load();
  }

  return (
    <div className="card">
      <input
        type="date"
        aria-label="Date"
        value={date}
        onChange={(e) => setDate(e.target.value)}
        style={{ maxWidth: 200 }}
      />
      {error && <Banner kind="error">{error}</Banner>}

      {!data ? (
        <Loading what="Loading" />
      ) : (
        <>
          {data.aisles.map((aisle) => (
            <div key={aisle.aisle_id} style={{ marginTop: "1.5rem" }}>
              <h3 style={{ margin: 0 }}>
                {aisleName(aisle.label)}
                <span className="small muted" style={{ fontWeight: 400 }}>
                  {" "}
                  · {aisle.percent_fed}% fed
                </span>
              </h3>
              {aisle.cages.length > 0 && (
                <div className="table-wrap" style={{ marginTop: "0.5rem" }}>
                  <table className="cage-table">
                    <colgroup>
                      <col />
                      <col className="col-fed" />
                      <col className="col-pct" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>Cage</th>
                        <th className="num">Fed</th>
                        <th className="num">%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {aisle.cages.map((cage) => (
                        <FeedRow
                          key={cage.cage_id}
                          cage={cage}
                          date={date}
                          onSave={save}
                          onManual={load}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ))}

          {data.aisles.length > 0 && (
            <>
              <div className="divider" />
              <strong>Today: {data.percent_fed}% fed</strong>
            </>
          )}
        </>
      )}
    </div>
  );
}

function FeedRow({
  cage,
  date,
  onSave,
  onManual,
}: {
  cage: FeedCage;
  date: string;
  onSave: (cageId: number, percent: number) => Promise<void>;
  onManual: () => Promise<void>;
}) {
  const done = cage.percent >= 100;
  const [value, setValue] = useState(String(cage.percent));
  const typing = useRef(false);
  // Ask for start/end before marking 100% a cage with no Clock session.
  const [asking, setAsking] = useState(false);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Follow the saved value unless the user is typing in this box.
  useEffect(() => {
    if (!typing.current) setValue(String(cage.percent));
  }, [cage.percent]);

  /** 100% needs a Clock start/end: ask for it if this cage has none. */
  const setPercent = (pct: number) => {
    if (pct === 100 && !cage.session) {
      const endAt = `${date}T${nowBrisbaneHM()}`;
      const planned = Math.round(cage.planned_minutes) || 30;
      setEnd(endAt);
      setStart(shiftLocal(endAt, -planned));
      setErr(null);
      setAsking(true);
      return false;
    }
    onSave(cage.cage_id, pct);
    return true;
  };

  const commit = () => {
    const n = Math.round(Number(value));
    if (value.trim() === "" || Number.isNaN(n)) {
      setValue(String(cage.percent));
      return;
    }
    const pct = Math.min(100, Math.max(0, n));
    if (pct === cage.percent) {
      setValue(String(pct));
      return;
    }
    // If we have to ask for times first, keep showing the saved value.
    setValue(String(setPercent(pct) ? pct : cage.percent));
  };

  async function confirm() {
    if (!start || !end) {
      setErr("Enter a start and an end.");
      return;
    }
    if (end < start) {
      setErr("End must be after start.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await api.clockManual(cage.cage_id, start, end);
      setAsking(false);
      await onManual();
    } catch {
      setErr("Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <tr>
        <td>
          <strong>{cage.code}</strong>
        </td>
        <td className="num">
          <input
            type="checkbox"
            className="feed-check"
            aria-label={`${cage.code} fully fed`}
            checked={done}
            disabled={asking}
            onChange={(e) => setPercent(e.target.checked ? 100 : 0)}
          />
        </td>
        <td className="num">
          {!done && (
            <input
              className="inline-input"
              type="number"
              inputMode="numeric"
              min={0}
              max={99}
              aria-label={`${cage.code} % fed`}
              value={value}
              disabled={asking}
              onFocus={(e) => {
                typing.current = true;
                e.target.select();
              }}
              onBlur={() => {
                typing.current = false;
                commit();
              }}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              }}
              style={{ maxWidth: 70 }}
            />
          )}
        </td>
      </tr>
      {asking && (
        <tr className="manual-row">
          <td colSpan={3}>
            <div className="btn-row">
              <input
                type="datetime-local"
                aria-label={`${cage.code} start`}
                value={start}
                onChange={(e) => setStart(e.target.value)}
                autoFocus
              />
              <input
                type="datetime-local"
                aria-label={`${cage.code} end`}
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
              <button
                className="btn primary small"
                onClick={confirm}
                disabled={busy}
              >
                {busy ? "Saving…" : "Save"}
              </button>
              <button
                className="btn ghost small"
                onClick={() => setAsking(false)}
                disabled={busy}
              >
                Cancel
              </button>
            </div>
            {err && <div className="small" style={{ color: "var(--danger)" }}>{err}</div>}
          </td>
        </tr>
      )}
    </>
  );
}
