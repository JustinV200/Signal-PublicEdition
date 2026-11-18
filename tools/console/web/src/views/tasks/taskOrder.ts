// The Tasks page's row order. The server sends active tasks most finished
// first, and that order also feeds the projector's task grid, so it stays as
// it is there; only this view lifts the rows that wait on the owner to the top.
import type { TaskInfo } from "../../api";

/**
 * Puts every `needs_you` task first, whatever its percent. A stable split:
 * within each half the server's order holds.
 * @param tasks the active tasks in the server's order
 * @returns a new array; the input is not changed
 */
export function needsYouFirst(tasks: TaskInfo[]): TaskInfo[] {
  const waiting = tasks.filter((task) => task.status === "needs_you");
  const rest = tasks.filter((task) => task.status !== "needs_you");
  return [...waiting, ...rest];
}
