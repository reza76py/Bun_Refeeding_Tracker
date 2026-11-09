import {
  type InputHTMLAttributes,
  type ReactNode,
} from "react";

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
