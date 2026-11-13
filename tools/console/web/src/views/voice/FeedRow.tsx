// One voice feed row: `HH:MM:SS  kind  text`. `heard` is quoted, `said` is
// plain, `note` is faint.
import type { VoiceEvent } from "../../api";
import { formatClockSeconds } from "../../time";
import styles from "./voice.module.css";

/** A heard / said / note row; `live` rows animate in. */
export function FeedRow({ event, live }: { event: VoiceEvent; live: boolean }) {
  const text = event.kind === "heard" ? `"${event.text}"` : event.text;
  const textClasses = [
    styles.text,
    event.kind === "note" && styles.note,
    live && "anim-row",
  ].filter(Boolean);
  return (
    <div className={styles.row}>
      <span className={styles.meta}>{formatClockSeconds(event.at)}</span>
      <span className={styles.meta}>{event.kind}</span>
      <span className={textClasses.join(" ")}>{text}</span>
    </div>
  );
}
