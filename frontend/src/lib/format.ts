/** Short duration: "45s", "4m 10s", "1h 15m"; "—" when not set. */
export function dur(seconds: number | null | undefined): string {
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

/** "9" is shown as "Aisle 9"; labels like "Aisle 9" or "Garden" stay as-is. */
export const aisleName = (label: string) =>
  /^\d+$/.test(label.trim()) ? `Aisle ${label.trim()}` : label;

/** Today's date (YYYY-MM-DD) in the store's time zone (Brisbane). */
export function todayBrisbane(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Australia/Brisbane",
  }).format(new Date());
}

/** Current Brisbane time as "HH:MM". */
export function nowBrisbaneHM(): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Australia/Brisbane",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date());
}

/** Shift a local "YYYY-MM-DDTHH:MM" by some minutes (no time-zone maths). */
export function shiftLocal(local: string, minutes: number): string {
  const ms = Date.parse(`${local}:00Z`) + minutes * 60_000;
  return new Date(ms).toISOString().slice(0, 16);
}

/** Date + time in Brisbane, e.g. "9 Nov 6:05" (24-hour). */
export function stamp(iso: string | null): string {
  if (!iso) return "—";
  const parts = new Intl.DateTimeFormat("en-AU", {
    timeZone: "Australia/Brisbane",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("day")} ${get("month")} ${Number(get("hour"))}:${get("minute")}`;
}

/** Duration with days: "1d 2h 5m", "2h 5m", "5m" ("0m" under a minute). */
export function durDays(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const total = Math.max(0, Math.floor(seconds / 60));
  const d = Math.floor(total / 1440);
  const h = Math.floor((total % 1440) / 60);
  const m = total % 60;
  if (d) return `${d}d ${h}h ${m}m`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
}
