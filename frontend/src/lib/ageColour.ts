import type { CSSProperties } from "react";
import type { RunningCage } from "../api/types";
import { aisleName } from "./format";

/** Colour by age of an unfinished cage: hue 120 (green) when fresh, sliding to
 * hue 0 (red) at AGE_CAP_HOURS; older stays red. Shared by the Plan aisle
 * lanes and the cage rows on Plan and Clock, so a cage and its aisle agree. */
export const AGE_CAP_HOURS = 72; // 3 days

export const ageHue = (seconds: number) =>
  120 * (1 - Math.min(1, Math.max(0, seconds) / (AGE_CAP_HOURS * 3600)));

/** Aisle lane tint on the Plan floor plan. */
export const laneTint = (hue: number) => ({
  background: `hsla(${hue}, 60%, 45%, 0.28)`,
  borderColor: `hsla(${hue}, 60%, 55%, 0.6)`,
  color: `hsl(${hue}, 70%, 78%)`,
});

/** Grey row background for a finished cage (ended on Clock or 100% on Today). */
const FINISHED_ROW = "rgba(150, 150, 150, 0.12)";

/** cage_id -> created_at (ms) for the unfinished cages. */
export const unfinishedIndex = (rows: RunningCage[]) =>
  new Map(rows.map((r) => [r.cage_id, Date.parse(r.created_at)]));

/** Row background for one cage: grey when finished; otherwise the lane
 * colour for its age (same hue, same tint as laneTint's background). */
export function cageRowStyle(
  cageId: number,
  unfinished: Map<number, number>,
  now: number
): CSSProperties {
  const created = unfinished.get(cageId);
  if (created === undefined) return { background: FINISHED_ROW };
  return { background: laneTint(ageHue((now - created) / 1000)).background };
}

/** Lane tint for an aisle with cages: the age of its OLDEST unfinished cage
 * (matched by aisle label, "5" == "Aisle 5"); all finished -> green. Same
 * result as the GI floor plan. */
export function aisleLaneTint(
  label: string,
  unfinished: RunningCage[],
  now: number
) {
  const name = aisleName(label).trim().toLowerCase();
  const oldest = unfinished
    .filter((u) => aisleName(u.aisle_label).trim().toLowerCase() === name)
    .reduce((min, u) => Math.min(min, Date.parse(u.created_at)), Infinity);
  return laneTint(oldest === Infinity ? 120 : ageHue((now - oldest) / 1000));
}

/** Same colour as cageRowStyle, as a CSS variable (--row-bg) for table rows,
 * so each cell can paint it and the row gets rounded ends (see .age-rows). */
export function cageRowVars(
  cageId: number,
  unfinished: Map<number, number>,
  now: number
): CSSProperties {
  const bg = cageRowStyle(cageId, unfinished, now).background;
  return { "--row-bg": bg } as CSSProperties;
}

