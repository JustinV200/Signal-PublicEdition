// Which actions ask before they run, and what they ask. One rule for every
// path (the Boards and Voice buttons and the palette): only a full calibrate
// (it flashes markers across the room), and loading a save or showing its live
// version over a drawing (the load, and a `tasks` redraw, clear the board
// first, so anything unsaved is lost). A `todo` redraw, the to-do list and the
// idle board are view switches that keep the drawing, and voice runs at once,
// so they never ask.
import type { ActionArgs, ActionName, BoardState } from "../../api";
import { isDrawingUp } from "../boards";
import { quoteName } from "./actionLabels";

// The one refresher that switches views (`todo show`) instead of redrawing the board.
const VIEW_SWITCH_REFRESHER = "todo";

/** The question to ask before `action` runs on `board`, or null when it runs at once. */
export function confirmPrompt(
  action: ActionName,
  args: ActionArgs | undefined,
  board: BoardState | undefined,
): string | null {
  if (action === "board.calibrate") return "Flash calibration markers on the projector?";
  if (isDrawingUp(board) && wipesBoard(action, args, board)) {
    // Quoted like the row the action leaves, so a hidden character shows here too.
    return `Replace what is on the projector with ${quoteName(args?.name ?? "")}? Anything unsaved there is lost.`;
  }
  return null;
}

/** Whether `action` clears the board before it draws: a load, or a save's non-`todo` redraw. */
function wipesBoard(
  action: ActionName,
  args: ActionArgs | undefined,
  board: BoardState | undefined,
): boolean {
  if (action === "board.load") return true;
  if (action !== "board.update") return false;
  const save = board?.saves.find((candidate) => candidate.name === args?.name);
  return save?.refresher !== VIEW_SWITCH_REFRESHER;
}
