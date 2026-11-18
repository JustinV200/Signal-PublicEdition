// One active task: `[review]  Brief phase 2  60%`, then a bold `YOU:` line
// when it waits on the owner, then its next step. The row's bottom rule is its
// progress bar (`--pct`), the number kept beside it. A row that needs the owner
// reads `! [needs you]` with a left bar; the tag's colour is only a second cue.
import type { CSSProperties } from "react";
import type { TaskInfo } from "../../api";
import styles from "./tasks.module.css";
import { statusTag } from "./taskWords";

/** A task row in the active list. */
export function TaskRow({ task }: { task: TaskInfo }) {
  const rowClass =
    task.status === "needs_you" ? `${styles.task} ${styles.needsYouRow}` : styles.task;
  return (
    <li className={rowClass} style={{ "--pct": `${task.pct}%` } as CSSProperties}>
      <span className={`${styles.tag} ${styles[task.status] ?? ""}`}>{statusTag(task)}</span>
      <span className={styles.name}>{task.name}</span>
      <span className={styles.pct}>{task.pct}%</span>
      {task.you && <div className={styles.you}>YOU: {task.you}</div>}
      {task.next && <div className={styles.next}>next: {task.next}</div>}
    </li>
  );
}
