import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { AdminCage } from "../api/types";
import { Banner, Loading } from "../components/ui";
import { aisleName, toBrisbaneLocal } from "../lib/format";

/** ADMIN only: change a cage's creation time to preview the age colours. */
export default function Settings() {
  const [cages, setCages] = useState<AdminCage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      // Finished cages (ended / 100%) are hidden on every page, here too:
      // keep only the cages the unfinished list still has.
      const [all, unfinished] = await Promise.all([
        api.adminCages(),
        api.graphRunning(),
      ]);
      const live = new Set(unfinished.map((u) => u.cage_id));
      setCages(all.filter((c) => live.has(c.cage_id)));
      setError(null);
    } catch {
      setError("Could not load.");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!cages) {
    return (
      <div className="card">
        {error ? <Banner kind="error">{error}</Banner> : <Loading what="Loading" />}
      </div>
    );
  }

  // Group by aisle, keeping the order the API returned.
  const groups: { label: string; cages: AdminCage[] }[] = [];
  for (const c of cages) {
    const g = groups.find((x) => x.label === c.aisle_label);
    if (g) g.cages.push(c);
    else groups.push({ label: c.aisle_label, cages: [c] });
  }

  return (
    <div className="card">
      <p className="muted small" style={{ marginTop: 0 }}>
        Changes a cage's creation time, which the age colours count from.
      </p>
      {error && <Banner kind="error">{error}</Banner>}
      {groups.length === 0 && <p className="muted">No cages.</p>}
      {groups.map((g, i) => (
        <div key={g.label} className={`aisle-block aisle-tone-${i % 4}`}>
          <h3 style={{ margin: 0 }}>{aisleName(g.label)}</h3>
          {g.cages.map((c) => (
            <CreatedRow key={c.cage_id} cage={c} onSaved={load} onError={setError} />
          ))}
        </div>
      ))}
    </div>
  );
}

function CreatedRow({
  cage,
  onSaved,
  onError,
}: {
  cage: AdminCage;
  onSaved: () => Promise<void>;
  onError: (msg: string | null) => void;
}) {
  const saved = toBrisbaneLocal(cage.created_at);
  const [value, setValue] = useState(saved);
  const [busy, setBusy] = useState(false);

  useEffect(() => setValue(saved), [saved]);

  async function save() {
    if (!value || value === saved) return;
    setBusy(true);
    onError(null);
    try {
      await api.adminSetCreated(cage.cage_id, value);
      await onSaved();
    } catch {
      onError(`Could not save ${cage.code}.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="clock-row">
      <strong>{cage.code}</strong>
      <div className="btn-row">
        <input
          type="datetime-local"
          aria-label={`${cage.code} created`}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          style={{ width: "auto" }}
        />
        <button
          className="btn primary small"
          onClick={save}
          disabled={busy || !value || value === saved}
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
    </div>
  );
}
