import type { ReactNode } from "react";
import { createPortal } from "react-dom";

/** A print-only A4 report. It is rendered straight into <body> (outside the
 * app) and hidden on screen; when printing, the app is hidden and only this
 * shows (see "Print report" in index.css). */
export function PrintReport({
  title,
  date,
  children,
}: {
  title: string;
  /** Already formatted, e.g. "Tue 10 Nov 2026". */
  date: string;
  children: ReactNode;
}) {
  return createPortal(
    <div className="print-report">
      <h1>{title}</h1>
      <p className="print-date">{date}</p>
      {children}
    </div>,
    document.body
  );
}
