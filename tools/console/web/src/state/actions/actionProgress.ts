// Where a button's request has got to, read off its delivery: `sending` until
// the POST returns, `working` while the server runs it, then `done` or
// `failed`. `sent` is only for rows from before buttons ran in the server
// (replayed history). Pure; the views derive it.
import type { ActionName } from "../../api";
import { toMs } from "../../time";
import type { LocalMessage } from "../reducer";

export type ActionProgress = "sending" | "sent" | "working" | "done" | "failed";

// shortcut: a request with no result stops counting as pending after this long,
// so a lost result cannot wedge the UI; the server gives up on a whiteboard
// command before this (actions/whiteboard_cli.py TIMEOUT_S).
export const PENDING_MAX_MS = 2 * 60 * 1000;

/** Progress of an action row. */
export function actionProgress(message: LocalMessage): ActionProgress {
  switch (message.delivery) {
    case "sending":
    case "done":
    case "failed":
      return message.delivery;
    case "running":
      return "working";
    default:
      return "sent";
  }
}

// A row is pending while it is a request this page sent (it has a local origin;
// a replayed row never pends, so a reload starts clean), is still sending or
// running, and is younger than PENDING_MAX_MS. The buttons and the scope share this.
function isPendingAction(message: LocalMessage, now: number): boolean {
  if (message.origin?.kind !== "action") return false;
  const progress = actionProgress(message);
  if (progress !== "sending" && progress !== "working") return false;
  return now - toMs(message.at) < PENDING_MAX_MS;
}

/** The action rows this page sent that are still running at `now`, oldest first. */
export function pendingRows(messages: readonly LocalMessage[], now: number): LocalMessage[] {
  return messages.filter((message) => isPendingAction(message, now));
}

/**
 * The action names still running at `now`. A later row for the same action
 * replaces an earlier one's verdict, so a retry pends again.
 */
export function pendingActions(messages: readonly LocalMessage[], now: number): Set<ActionName> {
  const pending = new Set<ActionName>();
  for (const message of messages) {
    if (message.origin?.kind !== "action") continue;
    if (isPendingAction(message, now)) pending.add(message.origin.action);
    else pending.delete(message.origin.action);
  }
  return pending;
}
