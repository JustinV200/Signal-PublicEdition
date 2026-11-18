// The Tasks page's words: the header's counts and the usage line. Pure, so
// they are easy to test. Every status is a word, so it also works
// for colourblind users; colour is only ever a second cue.
import type { TaskInfo, TasksPayload, UsageInfo, UsageWindow } from "../../api";
import { formatClock, formatRelative, toMs } from "../../time";

const STATUS_WORDS: Record<TaskInfo["status"], string> = {
  review: "review",
  building: "building",
  needs_you: "needs you",
  queued: "queued",
  done: "done",
};

const USAGE_LABEL = "Claude usage:";

/**
 * `[review]`: the state by word only (the whiteboard grid's status number is
 * not shown). A task waiting on the owner reads `! [needs you]`, so the mark
 * and the word, not just the colour, set it apart.
 */
export function statusTag(task: TaskInfo): string {
  const tag = `[${STATUS_WORDS[task.status]}]`;
  return task.status === "needs_you" ? `! ${tag}` : tag;
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

/**
 * `Claude usage: 5-hour window 42% (resets 14:10) · week 18% · 5 agents · updated 2m ago`.
 * @param usage the server's usage block, null when it sent none
 * @param now the clock the reset and age are read against, in ms
 */
export function usageWords(usage: UsageInfo | null, now: number): string {
  if (!usage) return `${USAGE_LABEL} unknown`;
  const age = usage.updatedAt ? `updated ${formatRelative(usage.updatedAt, now)}` : "no usage yet";
  const agents = `${usage.agents} ${usage.agents === 1 ? "agent" : "agents"}`;
  const parts = [
    windowWords("5-hour window", usage.fiveHour, now, true),
    windowWords("week", usage.sevenDay, now, false),
    agents,
    age,
  ];
  return `${USAGE_LABEL} ${parts.join(" · ")}`;
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
