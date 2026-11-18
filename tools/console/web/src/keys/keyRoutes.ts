// The window-level key decisions useGlobalKeys acts on, kept free of the DOM
// so they can be tested: which typed keys belong to the input line, and what
// Esc closes.
import type { InputMode } from "../state";

/** The parts of a KeyboardEvent the routing reads. */
export interface KeyInfo {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
}

/** What Esc closes: the input mode (palette or confirm), else help, else nothing. */
export type EscapeTarget = "mode" | "help" | "nothing";

// Focused fields that take typed letters themselves (a select's type-ahead picks an option).
const TEXT_FIELD_TAGS: ReadonlySet<string> = new Set(["TEXTAREA", "SELECT"]);
// The input types that take typed text; a checkbox or radio takes none, so letters go on to the input line.
const TEXT_INPUT_TYPES: ReadonlySet<string> = new Set([
  "",
  "text",
  "search",
  "email",
  "url",
  "tel",
  "password",
  "number",
]);
// Space presses a focused button or tab, so it stays with that control.
const SPACE = " ";

/** True for a key that types one character, with no Ctrl, Meta or Alt held. */
export function isPrintable(key: KeyInfo): boolean {
  return key.key.length === 1 && !key.ctrlKey && !key.metaKey && !key.altKey;
}

/**
 * Whether a typed key goes to the input line: any printable key but Space,
 * unless focus is in a field that takes text itself (a text-like input, a
 * textarea or a select; a checkbox or radio doesn't count).
 *
 * @param key The key pressed.
 * @param focusedTag The focused element's tagName (`BODY` when nothing has focus).
 * @param inputType The focused INPUT's `type` (ignored for other tags; none counts as text).
 * @returns True when the shell should focus the input so the key lands there.
 */
export function sendsToInput(
  key: KeyInfo,
  focusedTag: string | undefined,
  inputType?: string,
): boolean {
  return isPrintable(key) && key.key !== SPACE && !isTextField(focusedTag, inputType);
}

/** Whether the focused element takes typed letters itself. */
function isTextField(tag: string | undefined, inputType: string | undefined): boolean {
  if (tag === "INPUT") return TEXT_INPUT_TYPES.has((inputType ?? "").toLowerCase());
  return TEXT_FIELD_TAGS.has(tag ?? "");
}

/**
 * What Esc closes, nearest first: the palette or the confirm question (where
 * focus is), then help. With nothing open it closes nothing and only focuses
 * the input; it never changes view (Ctrl+1 is the way home).
 *
 * @param mode The input line's mode.
 * @param helpOpen Whether the help panel is open.
 */
export function escapeCloses(mode: InputMode["kind"], helpOpen: boolean): EscapeTarget {
  if (mode !== "text") return "mode";
  return helpOpen ? "help" : "nothing";
}
