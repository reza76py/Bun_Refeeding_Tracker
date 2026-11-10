import type { ReactNode } from "react";

/** One cage as a 3D wire roll cage (mesh trolley on wheels), tinted by age:
 * `hue` 120 (green, fresh) .. 0 (red, old) while unfinished; null = finished
 * (grey). The page's own controls go underneath via `children`. */
export function CageCard({
  code,
  hue,
  detail,
  children,
}: {
  code: string;
  /** From cageHue(): null when the cage is finished. */
  hue: number | null;
  /** Small line under the code, e.g. planned minutes. */
  detail?: ReactNode;
  children?: ReactNode;
}) {
  const finished = hue === null;
  const wire = finished ? "hsl(0, 0%, 62%)" : `hsl(${hue}, 55%, 62%)`;
  const face = finished ? "hsla(0, 0%, 60%, 0.10)" : `hsla(${hue}, 60%, 50%, 0.16)`;
  const side = finished ? "hsla(0, 0%, 60%, 0.06)" : `hsla(${hue}, 60%, 45%, 0.10)`;
  const glow = finished ? "transparent" : `hsla(${hue}, 70%, 50%, 0.18)`;
  return (
    <div
      className={finished ? "cage-card finished" : "cage-card"}
      style={{ ["--cage-glow" as string]: glow, ["--cage-wire" as string]: wire }}
    >
      <RollCage wire={wire} face={face} side={side} />
      <div className="cage-card-code">{code}</div>
      {detail && <div className="cage-card-detail">{detail}</div>}
      {children && <div className="cage-card-controls">{children}</div>}
    </div>
  );
}

/* Isometric roll cage. Front face 22..74 x 18..104; the back face is the
 * front shifted by (DX, -DY), giving the right side and top in perspective. */
const DX = 22;
const DY = 12;
const FX0 = 22;
const FX1 = 74;
const FY0 = 18;
const FY1 = 104;

function RollCage({ wire, face, side }: { wire: string; face: string; side: string }) {
  const vertsFront = [32.4, 42.8, 53.2, 63.6];
  const rows = [35.2, 52.4, 69.6, 86.8];
  const sideCols = [1 / 3, 2 / 3];
  return (
    <svg
      className="roll-cage"
      viewBox="0 0 110 128"
      role="img"
      aria-hidden="true"
      focusable="false"
    >
      {/* panels: back-right side, top, front (translucent tint) */}
      <polygon
        points={`${FX1},${FY0} ${FX1 + DX},${FY0 - DY} ${FX1 + DX},${FY1 - DY} ${FX1},${FY1}`}
        fill={side}
      />
      <polygon
        points={`${FX0},${FY0} ${FX1},${FY0} ${FX1 + DX},${FY0 - DY} ${FX0 + DX},${FY0 - DY}`}
        fill={side}
      />
      <rect x={FX0} y={FY0} width={FX1 - FX0} height={FY1 - FY0} fill={face} />

      <g stroke={wire} fill="none" strokeLinecap="round" strokeLinejoin="round">
        {/* hidden back edges, faint */}
        <g strokeWidth={0.8} opacity={0.35}>
          <line x1={FX0 + DX} y1={FY0 - DY} x2={FX0 + DX} y2={FY1 - DY} />
          <line x1={FX0 + DX} y1={FY1 - DY} x2={FX1 + DX} y2={FY1 - DY} />
          <line x1={FX0} y1={FY1} x2={FX0 + DX} y2={FY1 - DY} />
        </g>

        {/* side mesh (right face) */}
        <g strokeWidth={0.8} opacity={0.7}>
          {rows.map((y) => (
            <line key={`sr${y}`} x1={FX1} y1={y} x2={FX1 + DX} y2={y - DY} />
          ))}
          {sideCols.map((t) => (
            <line
              key={`sc${t}`}
              x1={FX1 + DX * t}
              y1={FY0 - DY * t}
              x2={FX1 + DX * t}
              y2={FY1 - DY * t}
            />
          ))}
        </g>

        {/* front mesh */}
        <g strokeWidth={0.9} opacity={0.85}>
          {vertsFront.map((x) => (
            <line key={`fv${x}`} x1={x} y1={FY0} x2={x} y2={FY1} />
          ))}
          {rows.map((y) => (
            <line key={`fh${y}`} x1={FX0} y1={y} x2={FX1} y2={y} />
          ))}
        </g>

        {/* frame */}
        <g strokeWidth={2}>
          <rect x={FX0} y={FY0} width={FX1 - FX0} height={FY1 - FY0} rx={1.5} />
          <polyline
            points={`${FX0},${FY0} ${FX0 + DX},${FY0 - DY} ${FX1 + DX},${FY0 - DY} ${FX1},${FY0}`}
          />
          <polyline
            points={`${FX1 + DX},${FY0 - DY} ${FX1 + DX},${FY1 - DY} ${FX1},${FY1}`}
          />
        </g>

        {/* base */}
        <polygon
          points={`${FX0 - 2},${FY1 + 3} ${FX1 + 2},${FY1 + 3} ${FX1 + DX + 2},${FY1 - DY + 3} ${FX0 + DX - 2},${FY1 - DY + 3}`}
          strokeWidth={1.6}
          fill={face}
        />
      </g>

      {/* wheels */}
      <g fill="#111" stroke={wire} strokeWidth={1.4}>
        <circle cx={FX0 + 3} cy={FY1 + 10} r={4} />
        <circle cx={FX1 - 3} cy={FY1 + 10} r={4} />
        <circle cx={FX1 + DX - 2} cy={FY1 - DY + 9} r={3.4} />
      </g>
    </svg>
  );
}
