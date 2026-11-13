// The Tasks page's words: the header's counts and the usage line. Pure, so
// they are easy to test. Every status is a number plus a word (the owner is
// colourblind; colour is only ever a second cue).
import type { TaskInfo, TasksPayload, UsageInfo, UsageWindow } from "../../api";
import { formatClock, formatRelative, toMs } from "../../time";

const STATUS_WORDS: Record<TaskInfo["status"], string> = {
  review: "review",
  building: "building",
  needs_you: "needs you",
  queued: "queued",
  done: "done",
};

/** `[1 review]`: the board's number and the word. */
export function statusTag(task: TaskInfo): string {
  return `[${task.number} ${STATUS_WORDS[task.status]}]`;
}

/** `4 active · 1 needs you · overall 58%`. */
export function headerCounts(tasks: TasksPayload): string {
  const parts = [`${tasks.active.length} active`];
  if (tasks.needsYou) parts.push(`${tasks.needsYou} needs you`);
  if (tasks.overallPct !== null) parts.push(`overall ${tasks.overallPct}%`);
  return parts.join(" · ");
}

function windowWords(
  label: string,
  window: UsageWindow | null,
  now: number,
  withReset: boolean,
): string {
  // The server drops a window once it resets; one that reset since then reads as unknown too.
  if (!window || toMs(window.resetsAt) <= now) return `${label} --`;
  const pct = `${label} ${Math.round(window.usedPct)}%`;
  return withReset ? `${pct} (resets ${formatClock(window.resetsAt)})` : pct;
}

/** `5h 42% (resets 14:10) · wk 18% · agents 5 · as of 2m ago`. */
export function usageWords(usage: UsageInfo | null, now: number): string {
  if (!usage) return "usage unknown";
  const age = usage.updatedAt ? `as of ${formatRelative(usage.updatedAt, now)}` : "no usage yet";
  return [
    windowWords("5h", usage.fiveHour, now, true),
    windowWords("wk", usage.sevenDay, now, false),
    `agents ${usage.agents}`,
    age,
  ].join(" · ");
}

/** `Queued: 6 tasks, none started` (or how many have). */
export function queuedHeading(queued: TaskInfo[]): string {
  const started = queued.filter((task) => task.pct > 0).length;
  const noun = queued.length === 1 ? "task" : "tasks";
  const progress = started ? `${started} started` : "none started";
  return `Queued: ${queued.length} ${noun}, ${progress}`;
}

/** How many task names a group lists before it is cut or toggled. */
export const NAMES_SHOWN = 6;

/** `Name 60%` for each task, joined with ` · `. */
export function taskNames(tasks: TaskInfo[]): string {
  return tasks.map((task) => `${task.name} ${task.pct}%`).join(" · ");
}
