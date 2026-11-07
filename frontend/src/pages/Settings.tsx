import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api/client";
import type {
  Aisle,
  AisleDetailMode,
  CatalogueSummary,
} from "../api/types";
import { Banner, Loading, NumberField } from "../components/ui";

export default function Settings() {
  const [aisles, setAisles] = useState<Aisle[]>([]);
  const [catalogue, setCatalogue] = useState<CatalogueSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    const [al, cat] = await Promise.all([api.aisles(), api.catalogue()]);
    setAisles(al);
    setCatalogue(cat);
  }, []);

  useEffect(() => {
    loadAll()
      .catch(() => setError("Could not load settings."))
      .finally(() => setLoading(false));
  }, [loadAll]);

  if (loading) return <Loading what="Loading settings" />;

  return (
    <div>
      <h1>Settings</h1>
      {error && <Banner kind="error">{error}</Banner>}

      <CatalogueCard
        aisles={aisles}
        catalogue={catalogue}
        onChanged={loadAll}
      />
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

/** Short duration: "45s", "4m 10s", "1h 15m"; "—" when not set. */
function dur(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) {
    const m = Math.floor(s / 60);
    const r = s % 60;
    return r ? `${m}m ${r}s` : `${m}m`;
  }
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m}m`;
}

const optNum = (v: number | "") => (v === "" ? null : v);

function CatalogueCard({
  aisles,
  catalogue,
  onChanged,
}: {
  aisles: Aisle[];
  catalogue: CatalogueSummary | null;
  onChanged: () => Promise<void>;
}) {
  const [label, setLabel] = useState("");
  const [mode, setMode] = useState<AisleDetailMode>("cages");
  const [justAdded, setJustAdded] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [added, setAdded] = useState<string | null>(null);
  const labelRef = useRef<HTMLInputElement>(null);

  async function removeAll() {
    const cages = aisles.reduce((n, a) => n + a.cages.length, 0);
    const bays = aisles.reduce((n, a) => n + a.bays.length, 0);
    if (
      !window.confirm(
        `Remove ALL information?

This permanently deletes ${aisles.length} ` +
          `aisle(s), ${cages} cage(s) and ${bays} bay(s), with their lines and ` +
          "times. This cannot be undone."
      )
    )
      return;
    setBusy(true);
    setError(null);
    setAdded(null);
    try {
      const r = await api.deleteAllAisles();
      setJustAdded(null);
      await onChanged();
      setAdded(`Removed everything (${r.deleted_aisles} aisle(s)).`);
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  }

  async function addAisle() {
    const trimmed = label.trim();
    if (!trimmed) return;
    setBusy(true);
    setError(null);
    setAdded(null);
    try {
      const created = await api.createAisle(trimmed, mode);
      setLabel("");
      await onChanged();
      // Jump straight to the new aisle's first input (cage or bay number).
      setJustAdded(created.id);
      setAdded(
        mode === "cages"
          ? `Saved "${created.label}". Now add its cages below (e.g. A10).`
          : `Saved "${created.label}". Now add its bays below (e.g. bay 3).`
      );
    } catch (e) {
      setError(errText(e));
      labelRef.current?.focus();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Aisles, cages & bays (catalogue)</h2>
      <ModePicker
        value={mode}
        onChange={setMode}
        label="How to enter this aisle's lines"
      />
      <form
        className="grid cols-3"
        style={{ alignItems: "end" }}
        onSubmit={(e) => {
          e.preventDefault();
          addAisle();
        }}
      >
        <div className="field">
          <label htmlFor="new-aisle-label">Aisle number / name</label>
          <input
            id="new-aisle-label"
            ref={labelRef}
            placeholder="e.g. 2 or Aisle 2"
            maxLength={40}
            value={label}
            onChange={(e) => setLabel(e.target.value)}
          />
        </div>
        <div />
        <div className="field">
          <label>&nbsp;</label>
          <button
            className="btn primary"
            type="submit"
            disabled={busy || !label.trim()}
          >
            {busy
              ? "Saving…"
              : mode === "cages"
                ? "Add aisle (cages)"
                : "Add aisle (bays)"}
          </button>
        </div>
      </form>
      {error && <Banner kind="error">{error}</Banner>}
      {added && <p className="small muted">✓ {added}</p>}
      {aisles.length === 0 && (
        <p className="muted">No aisles yet. Add one above to get started.</p>
      )}
      {aisles.map((aisle) => (
        <AisleBlock
          key={aisle.id}
          aisle={aisle}
          autoFocus={justAdded === aisle.id}
          onChanged={onChanged}
        />
      ))}

      {catalogue && (
        <p>
          <strong>
            Combined: {catalogue.combined_catalogue_lines.toLocaleString()} lines
            {catalogue.combined_estimated_seconds !== null &&
              ` · ${dur(catalogue.combined_estimated_seconds)}`}
          </strong>
          {catalogue.combined_estimated_seconds !== null && (
            <span className="small muted">
              {" "}
              (time = a cage's minutes, or lines × seconds per line, for the
              cages/bays that have a time)
            </span>
          )}
        </p>
      )}

      {aisles.length > 0 && (
        <>
          <div className="divider" />
          <div className="row-between">
            <span className="small muted">
              Delete every aisle, cage and bay you have entered.
            </span>
            <button
              className="btn danger"
              onClick={removeAll}
              disabled={busy}
            >
              Remove all
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function ModePicker({
  value,
  onChange,
  label,
  disabled,
}: {
  value: AisleDetailMode;
  onChange: (m: AisleDetailMode) => void;
  label: string;
  disabled?: boolean;
}) {
  const opts: { mode: AisleDetailMode; text: string }[] = [
    { mode: "cages", text: "By cages" },
    { mode: "bays", text: "By bays" },
  ];
  return (
    <div
      className="btn-row"
      role="radiogroup"
      aria-label={label}
      style={{ marginBottom: "0.5rem" }}
    >
      {opts.map((o) => (
        <button
          key={o.mode}
          type="button"
          role="radio"
          aria-checked={value === o.mode}
          className={value === o.mode ? "btn primary small" : "btn small"}
          onClick={() => onChange(o.mode)}
          disabled={disabled}
        >
          {o.text}
        </button>
      ))}
    </div>
  );
}

function AisleBlock({
  aisle,
  autoFocus,
  onChanged,
}: {
  aisle: Aisle;
  autoFocus: boolean;
  onChanged: () => Promise<void>;
}) {
  const mode = aisle.detail_mode;
  const nextBay =
    aisle.bays.reduce((m, b) => Math.max(m, b.bay_number), 0) + 1;
  const [renaming, setRenaming] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  // The add-cage / add-bay form is hidden behind a button, except on the
  // aisle that was just created.
  const [adding, setAdding] = useState(false);
  const [newLabel, setNewLabel] = useState(aisle.label);
  const [cageCode, setCageCode] = useState("");
  const [cageLines, setCageLines] = useState<number | "">("");
  // Seconds per line is kept after adding, so the next row reuses it.
  const [cageSpl, setCageSpl] = useState<number | "">("");
  const [cageMinutes, setCageMinutes] = useState<number | "">("");
  // How a new cage is entered: just its minutes, or lines x sec/line.
  const [cageEntry, setCageEntry] = useState<"minutes" | "lines">(
    aisle.cages.some((c) => c.minutes !== null) || aisle.cages.length === 0
      ? "minutes"
      : "lines"
  );
  const [bayNumber, setBayNumber] = useState<number | "">(nextBay);
  const [bayLines, setBayLines] = useState<number | "">("");
  const [baySpl, setBaySpl] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const cageCodeRef = useRef<HTMLInputElement>(null);
  const bayNumberRef = useRef<HTMLInputElement>(null);

  const focusFirst = () =>
    (mode === "cages" ? cageCodeRef : bayNumberRef).current?.focus();

  useEffect(() => {
    setAdding(autoFocus);
  }, [autoFocus]);

  useEffect(() => {
    if (adding) focusFirst();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adding]);

  async function run(fn: () => Promise<void>): Promise<boolean> {
    setBusy(true);
    setError(null);
    setMsg(null);
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
      if (!trimmed || trimmed === aisle.label) {
        setRenaming(false);
        return;
      }
      await api.updateAisle(aisle.id, { label: trimmed });
      setRenaming(false);
      await onChanged();
    });

  const switchMode = (m: AisleDetailMode) => {
    if (m === mode) return;
    run(async () => {
      await api.updateAisle(aisle.id, { detail_mode: m });
      await onChanged();
    });
  };

  const deleteAisle = () => {
    if (
      !window.confirm(
        `Delete ${aisle.label} with its ${aisle.cages.length} cage(s) and ` +
          `${aisle.bays.length} bay(s)? ` +
          "Logged cages keep their history but lose the aisle link."
      )
    )
      return;
    run(async () => {
      await api.deleteAisle(aisle.id);
      await onChanged();
    });
  };

  // --- cages ---
  const addCage = async () => {
    const code = cageCode.trim();
    if (!code) {
      setError("Type a cage number, e.g. A10.");
      cageCodeRef.current?.focus();
      return;
    }
    if (cageEntry === "minutes" && cageMinutes === "") {
      setError("Type the cage's time in minutes, e.g. 45.");
      return;
    }
    const ok = await run(async () => {
      await api.createAisleCage(
        aisle.id,
        cageEntry === "minutes"
          ? { code, minutes: cageMinutes === "" ? null : cageMinutes }
          : {
              code,
              lines: cageLines === "" ? 0 : cageLines,
              seconds_per_line: optNum(cageSpl),
            }
      );
      await onChanged();
    });
    if (ok) {
      setCageCode("");
      setCageLines("");
      setCageMinutes("");
      setAdding(false);
    } else {
      cageCodeRef.current?.focus();
    }
  };

  const deleteCage = (id: number, code: string) => {
    if (!window.confirm(`Delete cage ${code} from ${aisle.label}?`)) return;
    run(async () => {
      await api.deleteAisleCage(id);
      await onChanged();
    });
  };

  // --- bays ---
  const addBay = async () => {
    if (bayNumber === "" || bayNumber < 1) {
      setError("Bay number must be 1 or more.");
      bayNumberRef.current?.focus();
      return;
    }
    const ok = await run(async () => {
      await api.createBay(aisle.id, {
        bay_number: bayNumber,
        estimated_catalogue_lines: bayLines === "" ? 0 : bayLines,
        seconds_per_line: optNum(baySpl),
      });
      await onChanged();
    });
    if (ok) {
      setBayNumber(bayNumber + 1);
      setBayLines("");
      setAdding(false);
    } else {
      bayNumberRef.current?.focus();
    }
  };

  const deleteBay = (bayId: number, num: number) => {
    if (!window.confirm(`Delete bay ${num} from ${aisle.label}?`)) return;
    run(async () => {
      await api.deleteBay(bayId);
      await onChanged();
    });
  };

  const count = mode === "cages" ? aisle.cages.length : aisle.bays.length;
  const otherCount = mode === "cages" ? aisle.bays.length : aisle.cages.length;

  return (
    <div style={{ marginBottom: "1.5rem" }}>
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
              aria-label="Aisle label"
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
          <h3 style={{ margin: 0 }}>{aisle.label}</h3>
        )}
        <div className="btn-row">
          <span className="small muted">
            {count > 0
              ? `${count} ${mode === "cages" ? "cage" : "bay"}(s) · `
              : ""}
            {aisle.estimated_seconds !== null && aisle.catalogue_lines === 0
              ? dur(aisle.estimated_seconds)
              : `${aisle.catalogue_lines.toLocaleString()} lines` +
                (aisle.estimated_seconds !== null
                  ? ` · ${dur(aisle.estimated_seconds)}`
                  : "")}
            {aisle.rows_missing_time > 0 &&
              aisle.estimated_seconds !== null &&
              ` (${aisle.rows_missing_time} without time)`}
          </span>
          <button
            className="btn ghost small"
            onClick={() => setShowDetails((v) => !v)}
            aria-expanded={showDetails}
          >
            {showDetails ? "Less details" : "More details"}
          </button>
          {!renaming && (
            <button
              className="btn ghost small"
              onClick={() => setRenaming(true)}
              disabled={busy}
            >
              Rename
            </button>
          )}
          <button
            className="btn danger small"
            onClick={deleteAisle}
            disabled={busy}
          >
            Delete aisle
          </button>
        </div>
      </div>

      {showDetails && (
        <>
          <div className="btn-row" style={{ marginTop: "0.4rem" }}>
            <span className="small muted">Lines entered</span>
            <ModePicker
              value={mode}
              onChange={switchMode}
              label={`How ${aisle.label}'s lines are entered`}
              disabled={busy}
            />
          </div>
          {otherCount > 0 && (
            <p className="small muted">
              This aisle also has {otherCount}{" "}
              {mode === "cages" ? "bay(s)" : "cage(s)"} saved from before. They
              are kept but not counted while it is set to{" "}
              {mode === "cages" ? "cages" : "bays"}.
            </p>
          )}
        </>
      )}

      {error && <Banner kind="error">{error}</Banner>}
      {msg && <p className="small muted">{msg}</p>}

      {mode === "cages" ? (
        <>
          {aisle.cages.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <RowHeader first="Cage" withMinutes />
                </thead>
                <tbody>
                  {aisle.cages.map((cage) => (
                    <RowEditor
                      key={cage.id}
                      name={cage.code}
                      lines={cage.lines}
                      secondsPerLine={cage.seconds_per_line}
                      withMinutes
                      minutes={cage.minutes}
                      maxLines={1_000_000}
                      disabled={busy}
                      onSave={(lines, spl, minutes) =>
                        run(async () => {
                          await api.updateAisleCage(cage.id, {
                            lines,
                            seconds_per_line: spl,
                            minutes,
                          });
                          await onChanged();
                        })
                      }
                      onDelete={() => deleteCage(cage.id, cage.code)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="small muted">No cages yet.</p>
          )}

          {adding ? (
            <>
          <div
            className="btn-row"
            role="radiogroup"
            aria-label="How to enter the new cage"
            style={{ margin: "0.6rem 0 0.2rem" }}
          >
            <span className="small muted">Add a cage by</span>
            {(
              [
                ["minutes", "Minutes only"],
                ["lines", "Lines × sec/line"],
              ] as const
            ).map(([value, text]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={cageEntry === value}
                className={cageEntry === value ? "btn primary small" : "btn small"}
                onClick={() => {
                  setCageEntry(value);
                  cageCodeRef.current?.focus();
                }}
              >
                {text}
              </button>
            ))}
          </div>
          <form
            className={cageEntry === "minutes" ? "grid cols-3" : "grid cols-4"}
            style={{ alignItems: "end" }}
            onSubmit={(e) => {
              e.preventDefault();
              addCage();
            }}
          >
            <div className="field">
              <label htmlFor={`cage-code-${aisle.id}`}>Cage number</label>
              <input
                id={`cage-code-${aisle.id}`}
                ref={cageCodeRef}
                placeholder="e.g. A10"
                maxLength={20}
                value={cageCode}
                onChange={(e) => setCageCode(e.target.value)}
              />
            </div>
            {cageEntry === "minutes" ? (
              <NumberField
                label="Time for this cage"
                unit="minutes"
                min={0}
                max={1_440}
                placeholder="e.g. 45"
                value={cageMinutes}
                onChangeValue={setCageMinutes}
              />
            ) : (
              <>
                <NumberField
                  label="Lines in this cage"
                  unit="lines"
                  min={0}
                  max={1_000_000}
                  placeholder="e.g. 120"
                  value={cageLines}
                  onChangeValue={setCageLines}
                />
                <NumberField
                  label="Seconds per line"
                  unit="sec"
                  min={0}
                  max={3_600}
                  placeholder="e.g. 5"
                  value={cageSpl}
                  onChangeValue={setCageSpl}
                  note={
                    cageLines !== "" && cageSpl !== ""
                      ? `= ${dur(cageLines * cageSpl)} for this cage`
                      : undefined
                  }
                />
              </>
            )}
            <div className="field">
              <label>&nbsp;</label>
              <div className="btn-row">
                <button className="btn primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Add cage"}
                </button>
              </div>
            </div>
          </form>
            </>
          ) : (
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
        </>
      ) : (
        <>
          {aisle.bays.length > 0 ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <RowHeader first="Bay" />
                </thead>
                <tbody>
                  {aisle.bays.map((bay) => (
                    <RowEditor
                      key={bay.id}
                      name={`Bay ${bay.bay_number}`}
                      lines={bay.estimated_catalogue_lines}
                      secondsPerLine={bay.seconds_per_line}
                      maxLines={100_000}
                      disabled={busy}
                      onSave={(lines, spl) =>
                        run(async () => {
                          await api.updateBay(bay.id, {
                            estimated_catalogue_lines: lines,
                            seconds_per_line: spl,
                          });
                          await onChanged();
                        })
                      }
                      onDelete={() => deleteBay(bay.id, bay.bay_number)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="small muted">No bays yet.</p>
          )}

          {adding ? (
          <form
            className="grid cols-4"
            style={{ alignItems: "end" }}
            onSubmit={(e) => {
              e.preventDefault();
              addBay();
            }}
          >
            <div className="field">
              <label htmlFor={`bay-number-${aisle.id}`}>Bay number</label>
              <input
                id={`bay-number-${aisle.id}`}
                ref={bayNumberRef}
                type="number"
                inputMode="numeric"
                min={1}
                placeholder="e.g. 3"
                value={bayNumber}
                onChange={(e) =>
                  setBayNumber(
                    e.target.value === "" ? "" : Number(e.target.value)
                  )
                }
              />
            </div>
            <NumberField
              label="Lines in this bay"
              unit="lines"
              min={0}
              max={100_000}
              placeholder="e.g. 150"
              value={bayLines}
              onChangeValue={setBayLines}
            />
            <NumberField
              label="Seconds per line"
              unit="sec"
              min={0}
              max={3_600}
              placeholder="e.g. 5"
              value={baySpl}
              onChangeValue={setBaySpl}
              note={
                bayLines !== "" && baySpl !== ""
                  ? `= ${dur(bayLines * baySpl)} for this bay`
                  : undefined
              }
            />
            <div className="field">
              <label>&nbsp;</label>
              <div className="btn-row">
                <button className="btn primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Add bay"}
                </button>
              </div>
            </div>
          </form>
          ) : (
            <button
              className="btn primary small"
              type="button"
              style={{ marginTop: "0.6rem" }}
              onClick={() => setAdding(true)}
              disabled={busy}
            >
              + Add bay
            </button>
          )}
        </>
      )}

    </div>
  );
}

function RowHeader({
  first,
  withMinutes = false,
}: {
  first: string;
  withMinutes?: boolean;
}) {
  return (
    <tr>
      <th>{first}</th>
      <th>Lines</th>
      <th>Sec / line</th>
      {withMinutes && <th>Minutes</th>}
      <th className="num">Time</th>
      <th aria-label="Actions" />
    </tr>
  );
}

/** One cage or bay. Shows plain text with Edit / Delete; Edit turns the row
 * into inputs (lines, sec/line and, for cages, minutes) with Save / Cancel. */
function RowEditor({
  name,
  lines,
  secondsPerLine,
  withMinutes = false,
  minutes = null,
  maxLines,
  disabled,
  onSave,
  onDelete,
}: {
  name: string;
  lines: number;
  secondsPerLine: number | null;
  withMinutes?: boolean;
  minutes?: number | null;
  maxLines: number;
  disabled: boolean;
  onSave: (
    lines: number,
    spl: number | null,
    minutes: number | null
  ) => Promise<boolean>;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [l, setL] = useState<number | "">(lines);
  const [spl, setSpl] = useState<number | "">(secondsPerLine ?? "");
  const [mins, setMins] = useState<number | "">(minutes ?? "");

  const reset = () => {
    setL(lines);
    setSpl(secondsPerLine ?? "");
    setMins(minutes ?? "");
  };
  // Keep the edit boxes in sync with the latest saved values.
  useEffect(() => {
    if (!editing) reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lines, secondsPerLine, minutes, editing]);

  const savedTime =
    minutes !== null
      ? minutes * 60
      : secondsPerLine === null
        ? null
        : lines * secondsPerLine;

  // ---------- view mode: plain text ----------
  if (!editing) {
    const timeOnly = minutes !== null && lines === 0;
    return (
      <tr>
        <td>
          <strong>{name}</strong>
        </td>
        <td>{timeOnly ? "—" : lines.toLocaleString()}</td>
        <td>{secondsPerLine === null ? "—" : `${secondsPerLine}s`}</td>
        {withMinutes && <td>{minutes === null ? "—" : `${minutes} min`}</td>}
        <td className="num">
          <strong>{dur(savedTime)}</strong>
        </td>
        <td className="num">
          <div className="btn-row" style={{ justifyContent: "flex-end" }}>
            <button
              className="btn small"
              onClick={() => setEditing(true)}
              disabled={disabled}
              aria-label={`Edit ${name}`}
            >
              Edit
            </button>
            <button
              className="btn danger small"
              onClick={onDelete}
              disabled={disabled}
              aria-label={`Delete ${name}`}
            >
              Delete
            </button>
          </div>
        </td>
      </tr>
    );
  }

  // ---------- edit mode: inputs ----------
  const nLines = l === "" ? 0 : l;
  const nSpl = optNum(spl);
  const nMins = optNum(mins);
  const liveTime =
    nMins !== null ? nMins * 60 : nSpl === null ? null : nLines * nSpl;

  async function save() {
    const unchanged =
      nLines === lines && nSpl === secondsPerLine && nMins === minutes;
    if (unchanged || (await onSave(nLines, nSpl, nMins))) setEditing(false);
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
  const num = (v: string) => (v === "" ? "" : Number(v));

  return (
    <tr>
      <td>
        <strong>{name}</strong>
      </td>
      <td>
        <input
          className="inline-input"
          type="number"
          inputMode="numeric"
          min={0}
          max={maxLines}
          aria-label={`Lines for ${name}`}
          value={l}
          disabled={disabled}
          onKeyDown={onKey}
          onChange={(e) => setL(num(e.target.value))}
          autoFocus
        />
      </td>
      <td>
        <input
          className="inline-input"
          type="number"
          inputMode="numeric"
          min={0}
          max={3_600}
          placeholder="sec"
          aria-label={`Seconds per line for ${name}`}
          value={spl}
          disabled={disabled}
          onKeyDown={onKey}
          onChange={(e) => setSpl(num(e.target.value))}
        />
      </td>
      {withMinutes && (
        <td>
          <input
            className="inline-input"
            type="number"
            inputMode="numeric"
            min={0}
            max={1_440}
            placeholder="min"
            aria-label={`Minutes for ${name}`}
            title="When set, this is the cage's time (lines × sec/line is ignored)"
            value={mins}
            disabled={disabled}
            onKeyDown={onKey}
            onChange={(e) => setMins(num(e.target.value))}
          />
        </td>
      )}
      <td className="num">{dur(liveTime)}</td>
      <td className="num">
        <div className="btn-row" style={{ justifyContent: "flex-end" }}>
          <button
            className="btn primary small"
            onClick={save}
            disabled={disabled}
          >
            Save
          </button>
          <button
            className="btn ghost small"
            onClick={cancel}
            disabled={disabled}
          >
            Cancel
          </button>
        </div>
      </td>
    </tr>
  );
}
