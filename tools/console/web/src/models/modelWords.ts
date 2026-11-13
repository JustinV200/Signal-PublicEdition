// The model strip's words: what runs now, and how each picker option reads.
// Pure, so they are easy to test. A pick is always named in words, never
// shown by colour alone.
import type { ModelPick, ModelTarget } from "../api";

const CLAUDE_PREFIX = "claude-";
/** The server's word for a settings value it can't vouch for. */
export const UNRECOGNISED = "unrecognised";

export const NEXT_SESSION_NOTE = "applies to every new Signal session, not this one";
export const SWITCH_NOW_HINT =
  "To switch the running session, click the model name under the VS Code prompt box.";
export const VOICE_NOTE = "applies on your next request";
/** The pickers' placeholder while settings.local.json can't be read (never "use my user settings"). */
export const UNREADABLE_LABEL = "can't read settings";
export const UNREADABLE_REASON = "settings.local.json can't be read, so it can't be changed here";

/** `claude-opus-5-5` reads as `opus-5-5`; aliases stay as they are. */
export function shortModel(model: string): string {
  return model.startsWith(CLAUDE_PREFIX) ? model.slice(CLAUDE_PREFIX.length) : model;
}

/** `now: opus-5-5 · medium`, with `model unknown` / `effort unknown` for the gaps. */
export function nowWords(now: ModelPick | null): string {
  if (!now) return "now: no session has claimed the console";
  const model = now.model ? shortModel(now.model) : "model unknown";
  return `now: ${model} · ${now.effort ?? "effort unknown"}`;
}

/** One picker option: null is the orchestrator's "use my user settings". */
export function optionLabel(value: string | null): string {
  return value ?? "use my user settings";
}

/** The placeholder shown while the current value isn't one of the options. */
export function offListLabel(target: ModelTarget, value: string | null): string {
  if (value === null) return target === "voice" ? "audiohub.toml default" : optionLabel(null);
  return value === UNRECOGNISED ? "something unrecognised" : `other: ${value}`;
}
