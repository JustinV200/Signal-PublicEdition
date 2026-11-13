// The Done group: a few names by default, a labelled toggle for all of them.
// The choice lives in sessionStorage (guarded: storage can be blocked).
import { useState } from "react";
import type { TaskInfo } from "../../api";
import { Button } from "../../ui";
import styles from "./tasks.module.css";
import { NAMES_SHOWN, taskNames } from "./taskWords";

const STORAGE_KEY = "signal-console-tasks-done-open";

function readOpen(): boolean {
  try {
    return sessionStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeOpen(open: boolean): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  } catch {
    // Storage blocked: the choice holds for this page load only.
  }
}

/** "Done today: N" with its names; more than a few get a Show all / Show fewer button. */
export function DoneGroup({ tasks }: { tasks: TaskInfo[] }) {
  const [open, setOpen] = useState(readOpen);
  if (tasks.length === 0) return null;
  const canToggle = tasks.length > NAMES_SHOWN;
  const shown = canToggle && !open ? tasks.slice(0, NAMES_SHOWN) : tasks;
  const toggle = () => {
    writeOpen(!open);
    setOpen(!open);
  };
  return (
    <div className={styles.group}>
      <div className={styles.groupHead}>{`Done today: ${tasks.length}`}</div>
      <div className={styles.groupNames}>
        {taskNames(shown)}
      </div>
      {canToggle && (
        <Button expanded={open} onClick={toggle}>
          {open ? "Show fewer" : `Show all ${tasks.length} done`}
        </Button>
      )}
    </div>
  );
}
