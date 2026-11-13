// One active task: `[1 review]  Brief phase 2  60%`, then a bold `YOU:` line
// when it waits on the owner, then its next step. The status is a number and a
// word; the tag's colour is only a second cue.
import type { TaskInfo } from "../../api";
import styles from "./tasks.module.css";
import { statusTag } from "./taskWords";

/** A task row in the active list. */
export function TaskRow({ task }: { task: TaskInfo }) {
  return (
    <li className={styles.task}>
      <div className={styles.line}>
        <span className={`${styles.tag} ${styles[task.status] ?? ""}`}>{statusTag(task)}</span>
        <span className={styles.name}>{task.name}</span>
        <span className={styles.pct}>{task.pct}%</span>
      </div>
      {task.you && <div className={styles.you}>YOU: {task.you}</div>}
      {task.next && <div className={styles.next}>next: {task.next}</div>}
    </li>
  );
}
