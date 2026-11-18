// The row the result strip (app/ResultStrip) reports: the newest action this
// page sent, of any kind, once it has an outcome. A replayed row has no local
// origin, so a reload never shows an old result. A newer action replaces the
// last one's result; a done result also clears DONE_SHOW_MS after the page
// heard it, while a failed one stays (the strip keeps which one was dismissed).
import { toMs } from "../../time";
import type { LocalMessage } from "../types";
import { actionProgress } from "./actionProgress";

/** How long a done result stays on the strip. */
export const DONE_SHOW_MS = 30_000;

/** Epoch ms a done row leaves the strip; null for any other row (a failed one never times out). */
export function doneClearsAt(row: LocalMessage): number | null {
  if (actionProgress(row) !== "done") return null;
  // The done delivery set settledAt; the send time is only a fallback for the type.
  return (row.settledAt ?? toMs(row.at)) + DONE_SHOW_MS;
}

/**
 * The newest local action row at `now` when it is failed, or done less than
 * DONE_SHOW_MS ago; null when there is none, it is still running, or its done expired.
 */
export function lastActionRow(messages: readonly LocalMessage[], now: number): LocalMessage | null {
  const row = messages.findLast((message) => message.origin?.kind === "action");
  if (!row) return null;
  if (actionProgress(row) === "failed") return row;
  const clearsAt = doneClearsAt(row);
  return clearsAt !== null && now < clearsAt ? row : null;
}
