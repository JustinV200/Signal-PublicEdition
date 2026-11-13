// The newest Start/Stop row's outcome in words, shown under the buttons so a
// click that fails (or works) says so on the Voice page, not only in Chat.
import { actionProgress } from "../../state";
import type { LocalMessage } from "../../state";

const LABELS: Record<string, string> = { "voice.start": "Start", "voice.stop": "Stop" };

/** E.g. `Start: failed - a voice hub is already running`; null before any voice click. */
export function lastVoiceAction(messages: readonly LocalMessage[]): string | null {
  const row = messages.findLast(
    (message) => message.origin?.kind === "action" && message.origin.action in LABELS,
  );
  if (row?.origin?.kind !== "action") return null;
  const detail = row.error ?? row.result;
  return `${LABELS[row.origin.action]}: ${actionProgress(row)}${detail ? ` - ${detail}` : ""}`;
}
