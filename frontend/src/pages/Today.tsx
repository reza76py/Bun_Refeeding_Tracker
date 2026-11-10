import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { api } from "../api/client";
import type { FeedAisle, FeedCage, FeedSummary, RunningCage } from "../api/types";
import { CageCard } from "../components/CageCard";
import { PrintReport } from "../components/PrintReport";
import { useAuth } from "../auth";
import { LaneCages } from "../components/CageIcon";
import { Banner, Loading } from "../components/ui";
import {
  aisleName,
  liveCages,
  reportDate,
  nowBrisbaneHM,
  shiftLocal,
  todayBrisbane,
} from "../lib/format";
import { useRefetchOnFocus } from "../lib/useRefetchOnFocus";
import {
  aisleLaneTint,
  cageHue,
  unfinishedIndex,
  aisleRunningCount,
  runningIds,
} from "../lib/ageColour";

/** Same store floor plan as GI / Member (same lanes and labels). */
const TOP_ROW = [7, 6, 5, 4, 3, 2];
const BOTTOM_ROW = [8, 9, 10, 11, 12, 13, 14, 15, 16];
const ALL_LANES = [...TOP_ROW, ...BOTTOM_ROW];

/** The aisle a lane stands for: "Aisle 5", or a bare "5". */
const findAisle = (aisles: FeedAisle[], n: number) =>
  aisles.find(
    (a) => aisleName(a.label).trim().toLowerCase() === `aisle ${n}`
  );

/** Per cage: tick = fully fed (100%), or type how much %. Totals are weighted
 * by each cage's planned time. The manager first sees the floor plan; only
 * aisles with cages can be opened. */
export default function Today() {
  const { user } = useAuth();
  const [date, setDate] = useState(todayBrisbane);
  const [data, setData] = useState<FeedSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  // The aisle number open (null = show the floor plan).
  const [selected, setSelected] = useState<number | null>(null);
  // Unfinished cages (for the lane age colours) and the clock they age by.
  const [unfinished, setUnfinished] = useState<RunningCage[]>([]);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    if (!date) return;
    try {
      setData(await api.feedSummary(date));
      setError(null);
    } catch {
      setError("Could not load.");
    }
    // Colours are a hint only: a failure here must not break the page.
    api.graphRunning().then(setUnfinished, () => {});
    setNow(Date.now());
  }, [date]);

  useEffect(() => {
    setData(null);
    load();
    // Keep lane colours current as cages age.
    const t = window.setInterval(load, 60_000);
    return () => window.clearInterval(t);
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

  const dateInput = (
    <input
      type="date"
      aria-label="Date"
      value={date}
      onChange={(e) => setDate(e.target.value)}
      style={{ maxWidth: 200 }}
    />
  );

  if (!data) {
    return (
      <div className="card">
        {dateInput}
        {error ? <Banner kind="error">{error}</Banner> : <Loading what="Loading" />}
      </div>
    );
  }

  // MNG report (print only): % fed per cage and aisle, and the day, for the
  // selected date.
  const report =
    user?.role === "mng" ? (
      <PrintReport title="MNG Report" date={reportDate(data.date)}>
        {data.aisles
          .filter((a) => a.cages.length > 0)
          .map((a) => (
            <div key={a.aisle_id} className="print-aisle">
              <h2>
                {aisleName(a.label)} · {a.percent_fed}% fed
              </h2>
              <table>
                <thead>
                  <tr>
                    <th>Cage</th>
                    <th className="num">Fed</th>
                  </tr>
                </thead>
                <tbody>
                  {a.cages.map((c) => (
                    <tr key={c.cage_id}>
                      <td>{c.code}</td>
                      <td className="num">{c.percent}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        <p className="print-total">Day: {data.percent_fed}% fed</p>
      </PrintReport>
    ) : null;

  const open = selected === null ? undefined : findAisle(data.aisles, selected);

  // --- one aisle: its cages with the existing % fed controls ---
  if (selected !== null && open && liveCages(open.cages).length > 0) {
    const ages = unfinishedIndex(unfinished);
    const runningNow = runningIds(unfinished);
    return (
      <div className="card">
        {report}
        <div className="btn-row">
          <button className="btn ghost small" onClick={() => setSelected(null)}>
            ← Back
          </button>
          {dateInput}
        </div>
        {error && <Banner kind="error">{error}</Banner>}
        <div className={`aisle-block aisle-tone-${ALL_LANES.indexOf(selected) % 4}`}>
          <h3 style={{ margin: 0 }}>
            {aisleName(open.label)}
            <span className="small muted" style={{ fontWeight: 400 }}>
              {" "}
              · {open.percent_fed}% fed
            </span>
          </h3>
          <div className="cage-grid">
            {liveCages(open.cages).map((cage) => (
              <FeedRow
                key={cage.cage_id}
                cage={cage}
                hue={cageHue(cage.cage_id, ages, now)}
                spinning={runningNow.has(cage.cage_id)}
                date={date}
                onSave={save}
                onManual={load}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  // --- the floor plan: only aisles with cages can be opened ---
  const lane = (n: number) => {
    const aisle = findAisle(data.aisles, n);
    const cages = aisle ? liveCages(aisle.cages).length : 0;
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
  const anyCages = data.aisles.some((a) => a.cages.length > 0);

  return (
    <div className="card">
      {report}
      {dateInput}
      {error && <Banner kind="error">{error}</Banner>}
      <div className="floor-wrap" style={{ marginTop: "1rem" }}>
        <div className="floor" role="group" aria-label="Store floor plan">
          <div className="floor-row floor-top">{row(TOP_ROW)}</div>
          <div className="floor-row">{row(BOTTOM_ROW)}</div>
        </div>
      </div>
      {anyCages && (
        <>
          <div className="divider" />
          <strong>Today: {data.percent_fed}% fed</strong>
        </>
      )}
    </div>
  );
}

function FeedRow({
  cage,
  hue,
  spinning,
  date,
  onSave,
  onManual,
}: {
  cage: FeedCage;
  /** Age colour (null = finished -> grey). */
  hue: number | null;
  spinning: boolean;
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
    <CageCard code={cage.code} hue={hue} spinning={spinning}>
      <div className="btn-row feed-controls">
        <label className="feed-tick">
          <input
            type="checkbox"
            className="feed-check"
            aria-label={`${cage.code} fully fed`}
            checked={done}
            disabled={asking}
            onChange={(e) => setPercent(e.target.checked ? 100 : 0)}
          />
          <span className="small">Fed</span>
        </label>
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
        {!done && <span className="small muted">%</span>}
      </div>
      {asking && (
        <div className="manual-prompt">
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
          <div className="btn-row">
            <button className="btn primary small" onClick={confirm} disabled={busy}>
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
        </div>
      )}
    </CageCard>
  );
}
