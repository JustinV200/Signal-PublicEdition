// The sweep: a leading radius with a short trail fading out behind it, turning
// once per server keepalive while `sweeping`. Stopped, it rests at 0°; the
// `NO SIGNAL` words, not the stillness, say why. Reduced motion stops it too
// (radar.module.css).
import { CENTER, polar, sectorPath } from "./geometry";
import styles from "./radar.module.css";

// The trail: thin sectors fading out behind the leading edge.
const TRAIL_STEPS = 8;
const TRAIL_STEP_DEG = 5;
const TRAIL_MAX_OPACITY = 0.16;

/** The sweep; it turns only while `sweeping`. */
export function Sweep({ sweeping }: { sweeping: boolean }) {
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
