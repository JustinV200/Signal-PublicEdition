// The tasks waiting on the owner, cut at a cap: the readout gives the first few
// a row each and folds the rest into one `+16 more` row, so it never grows with
// the task list. The radar draws them all as one count (taskBlips.ts) from this
// same split, so the two always agree.
import type { TaskInfo, TasksPayload } from "../../api";

// How many needs-you tasks the readout shows one by one.
const NEEDS_YOU_SHOWN = 3;

export interface NeedsYou {
  /** The first NEEDS_YOU_SHOWN waiting tasks, in the payload's order. */
  shown: TaskInfo[];
  /** How many more wait behind them; 0 when all are shown. */
  folded: number;
}

/**
 * Splits the waiting tasks at the cap.
 * @param tasks the `tasks` payload, null before the first event
 * @returns the shown tasks and the count of the folded rest
 */
export function splitNeedsYou(tasks: TasksPayload | null): NeedsYou {
  const waiting = tasks?.active.filter((task) => task.status === "needs_you") ?? [];
  return {
    shown: waiting.slice(0, NEEDS_YOU_SHOWN),
    folded: Math.max(0, waiting.length - NEEDS_YOU_SHOWN),
  };
}
