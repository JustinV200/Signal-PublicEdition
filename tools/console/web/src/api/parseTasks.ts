// Shape checks for the `tasks` event (tools/console's tasks feed). A task
// with a bad id, name or status is dropped; the other fields fall back.
import { dictList, isDict, numberOrNull, stringOr } from "./parseFields";
import type { Dict } from "./parseFields";
import type { TaskInfo, TaskStatus, TasksPayload, UsageInfo, UsageWindow } from "./types";

const STATUSES: readonly TaskStatus[] = ["review", "building", "needs_you", "queued", "done"];

function parseTask(dict: Dict): TaskInfo | null {
  const status = STATUSES.find((name) => name === dict.status);
  if (typeof dict.id !== "string" || typeof dict.name !== "string" || !status) return null;
  return {
    id: dict.id,
    name: dict.name,
    pct: numberOrNull(dict.pct) ?? 0,
    status,
    number: numberOrNull(dict.number) ?? STATUSES.indexOf(status) + 1,
    next: stringOr(dict.next, ""),
    you: stringOr(dict.you, ""),
    updatedAt: stringOr(dict.updatedAt, ""),
  };
}

function parseTaskList(value: unknown): TaskInfo[] {
  return dictList(value)
    .map(parseTask)
    .filter((task): task is TaskInfo => task !== null);
}

function parseWindow(value: unknown): UsageWindow | null {
  if (!isDict(value)) return null;
  const usedPct = numberOrNull(value.usedPct);
  if (usedPct === null || typeof value.resetsAt !== "string") return null;
  return { usedPct, resetsAt: value.resetsAt };
}

function parseUsage(value: unknown): UsageInfo | null {
  if (!isDict(value)) return null;
  return {
    fiveHour: parseWindow(value.fiveHour),
    sevenDay: parseWindow(value.sevenDay),
    agents: numberOrNull(value.agents) ?? 0,
    updatedAt: stringOr(value.updatedAt, null),
  };
}

/** Checks a `tasks` event body. A malformed one reads as an empty list. */
export function parseTasksPayload(value: unknown): TasksPayload {
  const dict = isDict(value) ? value : {};
  return {
    updatedAt: stringOr(dict.updatedAt, null),
    active: parseTaskList(dict.active),
    queued: parseTaskList(dict.queued),
    done: parseTaskList(dict.done),
    needsYou: numberOrNull(dict.needsYou) ?? 0,
    overallPct: numberOrNull(dict.overallPct),
    usage: parseUsage(dict.usage),
  };
}
