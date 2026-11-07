import {
  useEffect,
  useState,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

// --- Theme toggle (light/dark, persisted) ----------------------------------
type Theme = "light" | "dark" | "system";

export function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setThemeState] = useState<Theme>(
    () => (localStorage.getItem("theme") as Theme) || "system"
  );
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);
  return [theme, setThemeState];
}

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const next: Record<Theme, Theme> = {
    system: "light",
    light: "dark",
    dark: "system",
  };
  const label: Record<Theme, string> = {
    system: "Auto",
    light: "Light",
    dark: "Dark",
  };
  return (
    <button
      className="btn ghost small"
      onClick={() => setTheme(next[theme])}
      title="Toggle light / dark / auto"
      aria-label={`Theme: ${label[theme]}`}
    >
      {label[theme]}
    </button>
  );
}

// --- Inputs ----------------------------------------------------------------
interface NumberFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  label: string;
  unit?: string;
  note?: string;
  value: number | "";
  onChangeValue: (v: number | "") => void;
}

export function NumberField({
  label,
  unit,
  note,
  value,
  onChangeValue,
  ...rest
}: NumberFieldProps) {
  return (
    <div className="field">
      <label>
        {label} {unit && <span className="unit">({unit})</span>}
      </label>
      <input
        type="number"
        inputMode="numeric"
        value={value}
        onChange={(e) =>
          onChangeValue(e.target.value === "" ? "" : Number(e.target.value))
        }
        {...rest}
      />
      {note && <span className="note">{note}</span>}
    </div>
  );
}

export function Banner({
  kind = "info",
  children,
}: {
  kind?: "info" | "warn" | "error";
  children: ReactNode;
}) {
  return <div className={`banner ${kind}`}>{children}</div>;
}

export function Stat({
  label,
  value,
  kind,
}: {
  label: string;
  value: ReactNode;
  kind?: "estimate" | "actual";
}) {
  return (
    <div className={`stat ${kind ?? ""}`}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return <p className="muted">{what}…</p>;
}
