// The Tasks page: what the orchestrator reports through `console tasks set`.
// The header gives the counts and the usage line; active tasks are listed
// most finished first, then the queued and done groups. The server sends the
// order; this view only words it. A read only: nothing here sends a request.
import type { TaskInfo } from "../../api";
import { useStore } from "../../state";
import { useTicker } from "../../time";
import { DoneGroup } from "./DoneGroup";
import styles from "./tasks.module.css";
import { TaskRow } from "./TaskRow";
import { NAMES_SHOWN, headerCounts, queuedHeading, taskNames, usageWords } from "./taskWords";

const TICK_MS = 30_000;
const EMPTY = "No tasks reported. The orchestrator writes them with console tasks set.";

function names(tasks: TaskInfo[]): string {
  const more = tasks.length > NAMES_SHOWN ? ` · + ${tasks.length - NAMES_SHOWN} more` : "";
  return taskNames(tasks.slice(0, NAMES_SHOWN)) + more;
}

/** A grouped line: its heading, then the names it holds. */
function Group({ heading, tasks }: { heading: string; tasks: TaskInfo[] }) {
  if (tasks.length === 0) return null;
  return (
    <div className={styles.group}>
      <div className={styles.groupHead}>{heading}</div>
      <div className={styles.groupNames}>{names(tasks)}</div>
    </div>
  );
}

/** The tasks view. */
export function TasksView() {
  const { tasks } = useStore().state;
  const now = useTicker(TICK_MS);
  const total = tasks ? tasks.active.length + tasks.queued.length + tasks.done.length : 0;

  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Tasks</span>
        {tasks && <span className={styles.counts}>{headerCounts(tasks)}</span>}
        <span className={styles.usage}>{usageWords(tasks?.usage ?? null, now)}</span>
      </div>
      {!tasks || total === 0 ? (
        <p className={styles.empty}>{EMPTY}</p>
      ) : (
        <>
          <ul className={styles.list}>
            {tasks.active.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
          </ul>
          <Group heading={queuedHeading(tasks.queued)} tasks={tasks.queued} />
          <DoneGroup tasks={tasks.done} />
        </>
      )}
    </div>
  );
}
