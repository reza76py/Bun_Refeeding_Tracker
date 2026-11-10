import { useCallback, useEffect, useState } from "react";
import { api, clockExportUrl } from "../api/client";
import type { ClockAisle, ClockSummary, RunningCage } from "../api/types";
import { CageCard } from "../components/CageCard";
import { LaneCages } from "../components/CageIcon";
import { Banner, Loading } from "../components/ui";
import { aisleName, durDays, stamp } from "../lib/format";
import { useRefetchOnFocus } from "../lib/useRefetchOnFocus";
import {
  aisleLaneTint,
  cageHue,
  unfinishedIndex,
  aisleRunningCount,
} from "../lib/ageColour";

/** Same store floor plan as the Plan page (same lanes and labels). */
const TOP_ROW = [7, 6, 5, 4, 3, 2];
const BOTTOM_ROW = [8, 9, 10, 11, 12, 13, 14, 15, 16];
const ALL_LANES = [...TOP_ROW, ...BOTTOM_ROW];

/** The aisle a lane stands for: "Aisle 5", or a bare "5". */
const findAisle = (aisles: ClockAisle[], n: number) =>
  aisles.find(
    (a) => aisleName(a.label).trim().toLowerCase() === `aisle ${n}`
  );

/** Per cage: Start when refeeding it begins, End when it finishes. Sessions
 * can run over several days and every one is kept as history. The member
 * first sees the floor plan; only aisles GI set up with cages can be opened. */
export default function Clock() {
  const [data, setData] = useState<ClockSummary | null>(null);
  // The aisle number open (null = show the floor plan).
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Unfinished cages (for the row age colours) and the clock they age by.
  const [unfinished, setUnfinished] = useState<RunningCage[]>([]);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    try {
      setData(await api.clockSummary());
      setError(null);
    } catch {
      setError("Could not load.");
    }
    // Colours are a hint only: a failure here must not break the page.
    api.graphRunning().then(setUnfinished, () => {});
    setNow(Date.now());
  }, []);

  useEffect(() => {
    load();
    // Keep row colours current as cages age.
    const t = window.setInterval(load, 60_000);
    return () => window.clearInterval(t);
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

  const open = selected === null ? undefined : findAisle(data.aisles, selected);

  // --- one aisle: its cages with Start / End / Cancel ---
  if (selected !== null && open && open.cages.length > 0) {
    const ages = unfinishedIndex(unfinished);
    return (
      <div className="card">
        <button className="btn ghost small" onClick={() => setSelected(null)}>
          ← Back
        </button>
        {error && <Banner kind="error">{error}</Banner>}
        <div className={`aisle-block aisle-tone-${ALL_LANES.indexOf(selected) % 4}`}>
          <h3 style={{ margin: 0 }}>{aisleName(open.label)}</h3>
          <div className="cage-grid">
            {open.cages.map((c) => {
              const off = busy === c.cage_id;
              const last = c.last_session;
              return (
                <CageCard
                  key={c.cage_id}
                  code={c.code}
                  hue={cageHue(c.cage_id, ages, now)}
                  spinning={c.open_session !== null}
                >
                  {c.open_session ? (
                    <>
                      <span className="small">
                        Running since {stamp(c.open_session.start_at)}
                      </span>
                      <div className="btn-row">
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
                      </div>
                    </>
                  ) : last ? (
                    <span className="small">
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
                </CageCard>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // --- the floor plan: only aisles with cages can be opened ---
  const lane = (n: number) => {
    const aisle = findAisle(data.aisles, n);
    const cages = aisle?.cages.length ?? 0;
    return (
      <button
        key={`lane-${n}`}
        type="button"
        className={cages ? "lane has-cages" : "lane lane-off"}
        style={aisle && cages ? aisleLaneTint(aisle.label, unfinished, now) : undefined}
        onClick={() => cages && setSelected(n)}
        disabled={!cages}
        aria-label={cages ? `Aisle ${n}, ${cages} cage(s)` : `Aisle ${n} (no cages)`}
      >
        <span className="lane-label">Aisle {n}</span>
        {cages > 0 && (
          <LaneCages
            count={cages}
            running={aisle ? aisleRunningCount(aisle.label, unfinished) : 0}
          />
        )}
      </button>
    );
  };
  const row = (lanes: number[]) =>
    lanes.flatMap((n) => [
      lane(n),
      <div key={`shelf-${n}`} className="shelf" aria-hidden="true" />,
    ]);

  return (
    <div className="card">
      {error && <Banner kind="error">{error}</Banner>}
      <div className="floor-wrap">
        <div className="floor" role="group" aria-label="Store floor plan">
          <div className="floor-row floor-top">{row(TOP_ROW)}</div>
          <div className="floor-row">{row(BOTTOM_ROW)}</div>
        </div>
      </div>
      <div className="divider" />
      <a className="small muted" href={clockExportUrl} download>
        Export CSV
      </a>
    </div>
  );
}
