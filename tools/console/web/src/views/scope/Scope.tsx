// The radar scope: one SVG with a faint face, range rings, a crosshair grid,
// a slow low-contrast sweep and the labelled blips from blips.ts. Pure
// drawing. The sweep only runs while `sweeping` (page visible) and stops
// under prefers-reduced-motion.
import type { Blip } from "./blips";
import styles from "./scope.module.css";

const SIZE = 400;
const CENTER = SIZE / 2;
const RADIUS = 184;
const RING_FRACTIONS = [1 / 3, 2 / 3, 1];
const TICK_EVERY_DEG = 30;
const TICK_LENGTH = 6;
// The sweep's trail: thin sectors fading out behind the leading edge.
const TRAIL_STEPS = 8;
const TRAIL_STEP_DEG = 5;
const TRAIL_MAX_OPACITY = 0.16;
const BLIP_HALF = 5;
const LABEL_GAP = 11;
const LABEL_BASELINE = 4;
const CENTER_LABEL_DROP = 20;
const PULSE_CLASSES: Record<NonNullable<Blip["pulse"]>, string> = {
  normal: "anim-pulse",
  slow: "anim-pulse-slow",
};

interface Point {
  x: number;
  y: number;
}

function polar(bearingDeg: number, range: number): Point {
  const radians = ((bearingDeg - 90) * Math.PI) / 180;
  return {
    x: CENTER + Math.cos(radians) * RADIUS * range,
    y: CENTER + Math.sin(radians) * RADIUS * range,
  };
}

function sectorPath(fromDeg: number, toDeg: number): string {
  const from = polar(fromDeg, 1);
  const to = polar(toDeg, 1);
  return `M ${CENTER} ${CENTER} L ${from.x} ${from.y} A ${RADIUS} ${RADIUS} 0 0 1 ${to.x} ${to.y} Z`;
}

function Grid() {
  const ticks = Array.from({ length: 360 / TICK_EVERY_DEG }, (_, i) => i * TICK_EVERY_DEG);
  return (
    <g className={styles.grid}>
      {RING_FRACTIONS.map((fraction) => (
        <circle key={fraction} cx={CENTER} cy={CENTER} r={RADIUS * fraction} />
      ))}
      <line x1={CENTER - RADIUS} y1={CENTER} x2={CENTER + RADIUS} y2={CENTER} />
      <line x1={CENTER} y1={CENTER - RADIUS} x2={CENTER} y2={CENTER + RADIUS} />
      {ticks.map((deg) => {
        const outer = polar(deg, 1);
        const inner = polar(deg, (RADIUS - TICK_LENGTH) / RADIUS);
        return <line key={deg} x1={inner.x} y1={inner.y} x2={outer.x} y2={outer.y} />;
      })}
    </g>
  );
}

function Sweep({ sweeping }: { sweeping: boolean }) {
  const edge = polar(0, 1);
  return (
    <g className={`${styles.sweep} ${sweeping ? styles.sweeping : ""}`}>
      {Array.from({ length: TRAIL_STEPS }, (_, i) => (
        <path
          key={i}
          d={sectorPath(-(i + 1) * TRAIL_STEP_DEG, -i * TRAIL_STEP_DEG)}
          opacity={TRAIL_MAX_OPACITY * (1 - i / TRAIL_STEPS)}
        />
      ))}
      <line className={styles.sweepEdge} x1={CENTER} y1={CENTER} x2={edge.x} y2={edge.y} />
    </g>
  );
}

function Mark({ shape, at }: { shape: Blip["shape"]; at: Point }) {
  if (shape === "ring")
    return <circle cx={at.x} cy={at.y} r={BLIP_HALF} className={styles.hollow} />;
  if (shape === "disc") return <circle cx={at.x} cy={at.y} r={BLIP_HALF} />;
  const square = (
    <rect x={at.x - BLIP_HALF} y={at.y - BLIP_HALF} width={BLIP_HALF * 2} height={BLIP_HALF * 2} />
  );
  if (shape === "square") return square;
  return <g transform={`rotate(45 ${at.x} ${at.y})`}>{square}</g>;
}

function BlipMark({ blip }: { blip: Blip }) {
  const at = polar(blip.bearingDeg, blip.range);
  const centred = blip.range === 0;
  const left = !centred && at.x > CENTER;
  return (
    <g className={blip.pulse ? PULSE_CLASSES[blip.pulse] : undefined}>
      <Mark shape={blip.shape} at={at} />
      <text
        className={styles.label}
        x={centred ? at.x : left ? at.x - LABEL_GAP : at.x + LABEL_GAP}
        y={centred ? at.y + CENTER_LABEL_DROP : at.y + LABEL_BASELINE}
        textAnchor={centred ? "middle" : left ? "end" : "start"}
      >
        {blip.label}
      </text>
    </g>
  );
}

/** The scope; the readout beside it carries the same facts as text. */
export function Scope({ blips, sweeping }: { blips: Blip[]; sweeping: boolean }) {
  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className={styles.scope} aria-hidden="true">
      <circle cx={CENTER} cy={CENTER} r={RADIUS} className={styles.face} />
      <Grid />
      <Sweep sweeping={sweeping} />
      <g className={styles.blips}>
        {blips.map((blip) => (
          <BlipMark key={blip.id} blip={blip} />
        ))}
      </g>
    </svg>
  );
}
