import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { api, ApiError } from "../api/client";
import type { Aisle, AisleCage, RunningCage } from "../api/types";
import { Banner, Loading } from "../components/ui";
import { aisleName, dur } from "../lib/format";
import { useRefetchOnFocus } from "../lib/useRefetchOnFocus";
import {
  ageHue,
  cageRowVars,
  laneTint,
  unfinishedIndex,
} from "../lib/ageColour";

/** Store floor plan: shelves are static blocks, the lanes between them are
 * the aisles. Top row left -> right: 7..2; bottom row: 8..16. */
const TOP_ROW = [7, 6, 5, 4, 3, 2];
const BOTTOM_ROW = [8, 9, 10, 11, 12, 13, 14, 15, 16];
const ALL_LANES = [...TOP_ROW, ...BOTTOM_ROW];

/** The saved aisle a lane stands for: "Aisle 5", or a bare "5". */
const findAisle = (aisles: Aisle[], n: number) =>
  aisles.find(
    (a) => aisleName(a.label).trim().toLowerCase() === `aisle ${n}`
  );


/** Plan: pick an aisle on the floor plan, then add / edit its cages. */
export default function Plan() {
  const [aisles, setAisles] = useState<Aisle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  // The aisle number open in the cage editor (null = show the map).
  const [selected, setSelected] = useState<number | null>(null);
  // Unfinished cages (for the lane age colours) and the clock they age by.
  const [unfinished, setUnfinished] = useState<RunningCage[]>([]);
  const [now, setNow] = useState(() => Date.now());

  const load = useCallback(async () => {
    setAisles(await api.aisles());
    // Colours are a hint only: a failure here must not break the plan.
    api.graphRunning().then(setUnfinished, () => {});
    setNow(Date.now());
  }, []);

  useEffect(() => {
    load()
      .catch(() => setError("Could not load aisles."))
      .finally(() => setLoading(false));
  }, [load]);
  useRefetchOnFocus(load);
  // Keep lane colours current as cages age.
  useEffect(() => {
    const t = window.setInterval(() => load().catch(() => {}), 60_000);
    return () => window.clearInterval(t);
  }, [load]);

  /** Open a lane: create "Aisle N" first if it doesn't exist yet. */
  async function openLane(n: number) {
    setError(null);
    if (findAisle(aisles, n)) {
      setSelected(n);
      return;
    }
    setBusy(true);
    try {
      await api.createAisle(`Aisle ${n}`, "cages");
      await load();
      setSelected(n);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeAll() {
    if (
      !window.confirm(
        `Remove ALL ${aisles.length} aisle(s) and their cages? This cannot be undone.`
      )
    )
      return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteAllAisles();
      setSelected(null);
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading what="Loading" />;

  const open = selected === null ? undefined : findAisle(aisles, selected);

  // --- one aisle's cage editor ---
  if (selected !== null && open) {
    return (
      <div className="card">
        <button
          className="btn ghost small"
          onClick={() => setSelected(null)}
        >
          ← Back
        </button>
        {error && <Banner kind="error">{error}</Banner>}
        <AisleBlock
          key={open.id}
          tone={ALL_LANES.indexOf(selected) % 4}
          aisle={open}
          autoOpen={open.cages.length === 0}
          onChanged={load}
          unfinished={unfinishedIndex(unfinished)}
          now={now}
        />
      </div>
    );
  }

  // --- the floor-plan map ---
  const total = sumTime(aisles.flatMap((a) => a.cages));
  const lane = (n: number) => {
    const aisle = findAisle(aisles, n);
    const cages = aisle?.cages.length ?? 0;
    let tint: ReturnType<typeof laneTint> | undefined;
    if (aisle && cages) {
      // The oldest unfinished cage in this aisle drives its colour;
      // all finished -> green.
      const name = aisleName(aisle.label).trim().toLowerCase();
      const oldest = unfinished
        .filter((u) => aisleName(u.aisle_label).trim().toLowerCase() === name)
        .reduce((min, u) => Math.min(min, Date.parse(u.created_at)), Infinity);
      tint = laneTint(oldest === Infinity ? 120 : ageHue((now - oldest) / 1000));
    }
    return (
      <button
        key={`lane-${n}`}
        type="button"
        className={cages ? "lane has-cages" : "lane"}
        style={tint}
        onClick={() => openLane(n)}
        disabled={busy}
        aria-label={`Aisle ${n}${cages ? `, ${cages} cage(s)` : ""}`}
      >
        <span className="lane-label">Aisle {n}</span>
        {cages > 0 && <span className="lane-count">{cages}</span>}
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

      {aisles.length > 0 && (
        <>
          <div className="divider" />
          <div className="row-between">
            <strong>Total: {dur(total)}</strong>
            <button className="btn danger" onClick={removeAll} disabled={busy}>
              Remove all
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function errText(e: unknown): string {
  if (!(e instanceof ApiError)) return "Request failed.";
  const d = e.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    return Object.values(d as Record<string, unknown>)
      .flat()
      .map(String)
      .join(" ");
  }
  return e.message;
}

/** Sum of the cages' times; null when none has a time. */
function sumTime(cages: AisleCage[]): number | null {
  const timed = cages.filter((c) => c.estimated_seconds !== null);
  if (timed.length === 0) return null;
  return timed.reduce((n, c) => n + (c.estimated_seconds ?? 0), 0);
}

const num = (v: string): number | "" => (v === "" ? "" : Number(v));

function AisleBlock({
  tone,
  aisle,
  autoOpen,
  onChanged,
  unfinished,
  now,
}: {
  tone: number;
  aisle: Aisle;
  autoOpen: boolean;
  onChanged: () => Promise<void>;
  /** cage_id -> created_at (ms) of unfinished cages, for row colours. */
  unfinished: Map<number, number>;
  now: number;
}) {
  const [renaming, setRenaming] = useState(false);
  const [newLabel, setNewLabel] = useState(aisle.label);
  const [adding, setAdding] = useState(false);
  const [code, setCode] = useState("");
  const [minutes, setMinutes] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setAdding(autoOpen);
  }, [autoOpen]);

  useEffect(() => {
    if (adding) codeRef.current?.focus();
  }, [adding]);

  async function run(fn: () => Promise<void>): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      await fn();
      return true;
    } catch (e) {
      setError(errText(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  const rename = () =>
    run(async () => {
      const trimmed = newLabel.trim();
      if (trimmed && trimmed !== aisle.label) {
        await api.updateAisle(aisle.id, { label: trimmed });
        await onChanged();
      }
      setRenaming(false);
    });

  const deleteAisle = () => {
    if (
      !window.confirm(
        `Delete ${aisleName(aisle.label)} and its ${aisle.cages.length} cage(s)?`
      )
    )
      return;
    run(async () => {
      await api.deleteAisle(aisle.id);
      await onChanged();
    });
  };

  const addCage = async () => {
    const c = code.trim();
    if (!c) {
      setError("Type a cage number, e.g. A10.");
      codeRef.current?.focus();
      return;
    }
    if (minutes === "") {
      setError("Type the cage's time in minutes, e.g. 45.");
      return;
    }
    const ok = await run(async () => {
      await api.createAisleCage(aisle.id, { code: c, minutes });
      await onChanged();
    });
    if (ok) {
      setCode("");
      setMinutes("");
      setAdding(false);
    } else {
      codeRef.current?.focus();
    }
  };

  const deleteCage = (cage: AisleCage) => {
    if (!window.confirm(`Delete cage ${cage.code} from ${aisleName(aisle.label)}?`)) return;
    run(async () => {
      await api.deleteAisleCage(cage.id);
      await onChanged();
    });
  };

  const time = sumTime(aisle.cages);

  return (
    <div className={`aisle-block aisle-tone-${tone}`}>
      <div className="row-between">
        {renaming ? (
          <form
            className="btn-row"
            onSubmit={(e) => {
              e.preventDefault();
              rename();
            }}
          >
            <input
              aria-label="Aisle number"
              maxLength={40}
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              autoFocus
            />
            <button className="btn primary small" type="submit" disabled={busy}>
              Save
            </button>
            <button
              className="btn ghost small"
              type="button"
              onClick={() => {
                setNewLabel(aisle.label);
                setRenaming(false);
              }}
            >
              Cancel
            </button>
          </form>
        ) : (
          <h3 style={{ margin: 0 }}>
            {aisleName(aisle.label)}
            {time !== null && (
              <span className="small muted" style={{ fontWeight: 400 }}>
                {" "}
                · {dur(time)}
              </span>
            )}
          </h3>
        )}
        <div className="btn-row">
          {!renaming && (
            <button
              className="btn ghost small"
              onClick={() => setRenaming(true)}
              disabled={busy}
            >
              Edit
            </button>
          )}
          <button
            className="btn danger small"
            onClick={deleteAisle}
            disabled={busy}
          >
            Delete
          </button>
        </div>
      </div>

      {error && <Banner kind="error">{error}</Banner>}

      {(aisle.cages.length > 0 || adding) && (
        <div className="table-wrap" style={{ marginTop: "0.5rem" }}>
          <table className="cage-table age-rows">
            <colgroup>
              <col />
              <col className="col-time" />
              <col className="col-actions" />
            </colgroup>
            <thead>
              <tr>
                <th>Cage</th>
                <th className="num">Time</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {aisle.cages.map((cage) => (
                <CageRow
                  key={cage.id}
                  cage={cage}
                  rowStyle={cageRowVars(cage.id, unfinished, now)}
                  disabled={busy}
                  onSave={(c, m) =>
                    run(async () => {
                      await api.updateAisleCage(cage.id, { code: c, minutes: m });
                      await onChanged();
                    })
                  }
                  onDelete={() => deleteCage(cage)}
                />
              ))}
              {adding && (
                <tr>
                  <td>
                    <input
                      ref={codeRef}
                      className="inline-input"
                      aria-label="Cage number"
                      placeholder="Cage number"
                      maxLength={20}
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addCage();
                        }
                      }}
                    />
                  </td>
                  <td className="num">
                    <input
                      className="inline-input"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      max={1_440}
                      aria-label="Minutes"
                      placeholder="Minutes"
                      value={minutes}
                      onChange={(e) => setMinutes(num(e.target.value))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addCage();
                        }
                      }}
                    />
                  </td>
                  <td className="num">
                    <div className="btn-row" style={{ justifyContent: "flex-end" }}>
                      <button
                        className="btn primary small"
                        type="button"
                        onClick={addCage}
                        disabled={busy}
                      >
                        {busy ? "Saving…" : "Add"}
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {!adding && (
        <button
          className="btn primary small"
          type="button"
          style={{ marginTop: "0.6rem" }}
          onClick={() => setAdding(true)}
          disabled={busy}
        >
          + Add cage
        </button>
      )}
    </div>
  );
}

/** One cage: text with Edit / Delete; Edit shows cage number + minutes. */
function CageRow({
  cage,
  rowStyle,
  disabled,
  onSave,
  onDelete,
}: {
  cage: AisleCage;
  /** Age colour: grey when finished, green -> red while unfinished. */
  rowStyle: CSSProperties;
  disabled: boolean;
  onSave: (code: string, minutes: number | null) => Promise<boolean>;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [code, setCode] = useState(cage.code);
  const [mins, setMins] = useState<number | "">(cage.minutes ?? "");

  const reset = () => {
    setCode(cage.code);
    setMins(cage.minutes ?? "");
  };
  useEffect(() => {
    if (!editing) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cage.code, cage.minutes, editing]);

  if (!editing) {
    return (
      <tr className="age-row" style={rowStyle}>
        <td>
          <strong>{cage.code}</strong>
        </td>
        <td className="num">
          <strong>{dur(cage.estimated_seconds)}</strong>
        </td>
        <td className="num">
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button
              className="btn small"
              onClick={() => setEditing(true)}
              disabled={disabled}
              aria-label={`Edit ${cage.code}`}
            >
              Edit
            </button>
            <button
              className="btn danger small"
              onClick={onDelete}
              disabled={disabled}
              aria-label={`Delete ${cage.code}`}
            >
              Delete
            </button>
          </div>
        </td>
      </tr>
    );
  }

  const nMins = mins === "" ? null : mins;
  async function save() {
    const c = code.trim();
    const unchanged = c === cage.code && nMins === cage.minutes;
    if (unchanged || (await onSave(c, nMins))) setEditing(false);
  }
  const cancel = () => {
    reset();
    setEditing(false);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      save();
    } else if (e.key === "Escape") {
      cancel();
    }
  };

  return (
    <tr className="age-row" style={rowStyle}>
      <td>
        <input
          className="inline-input"
          aria-label="Cage number"
          maxLength={20}
          value={code}
          disabled={disabled}
          onKeyDown={onKey}
          onChange={(e) => setCode(e.target.value)}
          autoFocus
        />
      </td>
      <td className="num">
        <input
          className="inline-input"
          type="number"
          inputMode="numeric"
          min={0}
          max={1_440}
          placeholder="min"
          aria-label={`Minutes for ${cage.code}`}
          value={mins}
          disabled={disabled}
          onKeyDown={onKey}
          onChange={(e) => setMins(num(e.target.value))}
        />
      </td>
      <td className="num">
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button className="btn primary small" onClick={save} disabled={disabled}>
            Save
          </button>
          <button className="btn ghost small" onClick={cancel} disabled={disabled}>
            Cancel
          </button>
        </div>
      </td>
    </tr>
  );
}
