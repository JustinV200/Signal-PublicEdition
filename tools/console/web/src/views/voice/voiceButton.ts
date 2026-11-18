// The Voice view's one button: its label follows Voice. `Start voice` while
// it is stopped; `Stop voice` while it runs, `starting` included, because the
// server lets a stop through while a start is still loading Voice, so a slow
// or hung start can be stopped. It reads "Working…" only while the action
// named on it is itself pending.
import type { ActionName, VoiceState } from "../../api";

export interface VoiceButtonInfo {
  action: ActionName;
  label: string;
  /** The named action is on its way: the button reads "Working…" and ignores clicks. */
  pending: boolean;
}

/** The button for `voice` (undefined before the first snapshot reads as stopped). */
export function voiceButton(
  voice: VoiceState | undefined,
  pending: ReadonlySet<ActionName>,
): VoiceButtonInfo {
  // A hub that is `starting` reports running, so it gets Stop.
  const action: ActionName = voice?.running ? "voice.stop" : "voice.start";
  return {
    action,
    label: action === "voice.stop" ? "Stop voice" : "Start voice",
    pending: pending.has(action),
  };
}
