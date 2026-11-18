// The radar's still parts: the face (a radial falloff, brightest at the
// centre), the range rings, the crosshair with 30° ticks, and the sector
// boundaries drawn a little stronger than the crosshair. Pure drawing.
import { CENTER, polar, RADIUS } from "./geometry";
import styles from "./radar.module.css";
import { RINGS, SECTORS } from "./scale";

const TICK_EVERY_DEG = 30;
const TICK_LENGTH = 6;
// Only one scope is ever on the page, so a fixed id is unique.
const FALLOFF_ID = "scope-face-falloff";

function Face() {
  return (
    <>
      <defs>
        <radialGradient id={FALLOFF_ID}>
          <stop offset="0" className={styles.falloffCentre} />
          <stop offset="1" className={styles.falloffRim} />
        </radialGradient>
      </defs>
      <circle
        cx={CENTER}
        cy={CENTER}
        r={RADIUS}
        className={styles.face}
        fill={`url(#${FALLOFF_ID})`}
      />
    </>
  );
}

function Spoke({ deg, inner = 0 }: { deg: number; inner?: number }) {
  const from = polar(deg, inner);
  const to = polar(deg, 1);
  return <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} />;
}

/** Face, rings, crosshair, ticks and sector boundaries. */
export function Grid() {
  const ticks = Array.from({ length: 360 / TICK_EVERY_DEG }, (_, i) => i * TICK_EVERY_DEG);
  const tickInner = (RADIUS - TICK_LENGTH) / RADIUS;
  return (
    <>
      <Face />
      <g className={styles.grid}>
        {RINGS.map(({ fraction }) => (
          <circle key={fraction} cx={CENTER} cy={CENTER} r={RADIUS * fraction} />
        ))}
        <line x1={CENTER - RADIUS} y1={CENTER} x2={CENTER + RADIUS} y2={CENTER} />
        <line x1={CENTER} y1={CENTER - RADIUS} x2={CENTER} y2={CENTER + RADIUS} />
        {ticks.map((deg) => (
          <Spoke key={deg} deg={deg} inner={tickInner} />
        ))}
      </g>
      <g className={styles.boundaries}>
        {Object.values(SECTORS).map((sector) => (
          <Spoke key={sector.name} deg={sector.fromDeg} />
        ))}
      </g>
    </>
  );
}
