// Human text for an action while its row is still `sending`. The server's
// echo replaces it with the canonical wording once the action is accepted, so
// these use the same words as the server and the buttons. The palette's
// Commands use them too, so a command reads like the row it leaves.
import type { ActionArgs, ActionName } from "../../api";

// Characters a save name could hide behind: controls, bidi and other invisible
// format characters, line and paragraph separators and lone surrogates (by
// category), plus the default-ignorable letters and marks no category catches
// (Hangul fillers, variation selectors, the combining grapheme joiner and the
// like). That second part is an explicit list, the same as the server's
// _INVISIBLE_RANGES, so a Unicode update on one side can't make them differ.
const HIDDEN_CHARACTERS =
  /[\p{Cc}\p{Cf}\p{Zl}\p{Zp}\p{Cs}\u034F\u115F-\u1160\u17B4-\u17B5\u180B-\u180F\u2065\u3164\uFE00-\uFE0F\uFFA0\uFFF0-\uFFF8\u{E0000}-\u{E0FFF}]/gu;
const HEX_DIGITS = 4;

/** `\uXXXX` for each UTF-16 unit of `char` (an astral one becomes a pair, like JSON's). */
function escapeUnits(char: string): string {
  let escaped = "";
  for (let index = 0; index < char.length; index += 1) {
    escaped += `\\u${char.charCodeAt(index).toString(16).padStart(HEX_DIGITS, "0")}`;
  }
  return escaped;
}

/**
 * A save name in double quotes, shown as typed except for quotes, newlines and
 * hidden characters, which are escaped so a name can't pass for the words
 * around it. Gives exactly what the server's `_quoted` (actions/plans.py) does,
 * so a row doesn't change as the server's echo lands.
 */
export function quoteName(name: string): string {
  return JSON.stringify(name).replace(HIDDEN_CHARACTERS, escapeUnits);
}

/** Plain-language label for an action, e.g. `Send to projector: "lecture"`. */
export function actionLabel(action: ActionName, args?: ActionArgs): string {
  const name = quoteName(args?.name ?? "");
  switch (action) {
    case "voice.start":
      return "Start voice";
    case "voice.stop":
      return "Stop voice";
    case "board.load":
      return `Send to projector: ${name}`;
    case "board.todo":
      return "Send to projector: to-do list";
    case "board.idle":
      return "Send to projector: idle board";
    case "board.realign":
      return "Realign whiteboard";
    case "board.calibrate":
      return "Full calibrate";
    case "board.update":
      return `Show live version: ${name}`;
  }
}
