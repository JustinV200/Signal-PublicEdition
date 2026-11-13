// A faint centred label (`today`, `yesterday`, `Mon 13 Oct`) where the day changes.
import { formatDayLabel, useTicker } from "../../time";
import type { TimeLike } from "../../time";
import styles from "./chat.module.css";

// Only a day change can alter the label, so a minute's staleness is fine.
const TICK_MS = 60_000;

/** Marks the start of a new calendar day in the stream; `today` rolls over at midnight. */
export function DateDivider({ at }: { at: TimeLike }) {
  const now = useTicker(TICK_MS);
  return <div className={styles.divider}>{formatDayLabel(at, now)}</div>;
}
