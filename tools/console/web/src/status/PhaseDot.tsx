// The voice dot: ui's disc when running, its ring when stopped; starting and
// thinking pulse, speaking shows three bars. The phase word next to it carries the meaning.
import type { VoiceState } from "../api";
import { Mark } from "../ui";
import styles from "./status.module.css";

export type DotPhase = "starting" | "listening" | "thinking" | "speaking" | "stopped";

const BAR_COUNT = 3;

/** The dot phase for a voice state: `stopped` unless running, `listening` for any other phase. */
export function toDotPhase(voice: VoiceState | undefined): DotPhase {
  if (!voice?.running) return "stopped";
  const { phase } = voice;
  return phase === "starting" || phase === "thinking" || phase === "speaking" ? phase : "listening";
}

/** Decorative; the adjacent text says the phase, so this is hidden from readers. */
export function PhaseDot({ phase }: { phase: DotPhase }) {
  if (phase === "speaking") {
    return (
      <span className={styles.bars} aria-hidden="true">
        {Array.from({ length: BAR_COUNT }, (_, i) => (
          <span key={i} className={`${styles.speakBar} anim-bar`} />
        ))}
      </span>
    );
  }
  const stopped = phase === "stopped";
  const classes = [styles.dot];
  if (stopped) classes.push(styles.hollow);
  if (phase === "thinking" || phase === "starting") classes.push("anim-pulse");
  return (
    <span className={classes.join(" ")} aria-hidden="true">
      <Mark shape={stopped ? "ring" : "disc"} />
    </span>
  );
}
