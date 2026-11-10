/** Small 3D wire roll-cage icon for the floor-plan lanes. Drawn in
 * currentColor, so it takes the lane's (age-tinted) text colour. */
export function CageIcon({ size = 18 }: { size?: number }) {
  return (
    <svg
      className="cage-icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {/* side + top panels (back, in perspective) */}
      <path d="M15 5 L19 3 L19 17 L15 19 Z" fill="currentColor" fillOpacity="0.12" strokeWidth="1.2" />
      <path d="M5 5 L9 3 L19 3 L15 5 Z" fill="currentColor" fillOpacity="0.12" strokeWidth="1.2" />
      {/* front frame */}
      <rect x="5" y="5" width="10" height="14" rx="0.6" strokeWidth="1.6" />
      {/* mesh */}
      <path
        d="M8.3 5v14M11.7 5v14M5 9.7h10M5 14.3h10M17 4v14"
        strokeWidth="0.9"
        opacity="0.8"
      />
      {/* wheels */}
      <circle cx="6.5" cy="21" r="1.3" fill="currentColor" strokeWidth="0" />
      <circle cx="13.5" cy="21" r="1.3" fill="currentColor" strokeWidth="0" />
      <circle cx="18.5" cy="19" r="1.1" fill="currentColor" strokeWidth="0" />
    </svg>
  );
}

/** Most icons drawn in one lane; beyond this a "+N" shows the rest. */
const MAX_LANE_ICONS = 9;

/** One small cage icon per cage in the lane (e.g. 3 cages -> 3 icons). */
export function LaneCages({ count }: { count: number }) {
  const shown = Math.min(count, MAX_LANE_ICONS);
  return (
    <span className="lane-cages" aria-hidden="true">
      {Array.from({ length: shown }, (_, i) => (
        <CageIcon key={i} size={13} />
      ))}
      {count > shown && <span className="lane-more">+{count - shown}</span>}
    </span>
  );
}

