// The mock console's fake run of a board button: how the whiteboard's state
// changes and what the server says when done. Split out of mock-server.mjs,
// which owns the live state and swaps in the board this returns.
import { BOARD_ITEMS } from "../mock-state.mjs";
import { boardResult, boardStep, boardView } from "./mock-actions.mjs";

/**
 * Run a board action against `board`, like the real whiteboard would.
 * @param {object} board The current /api/state `board` block (not changed).
 * @param {{action: string, name?: string, saves: object[], oldWhiteboard: boolean}} run
 *   The action and its save name, this run's saves, and `--old-whiteboard`.
 * @returns {{board: object, result: string}} The new board block and the done words.
 */
export function runBoardAction(board, { action, name, saves, oldWhiteboard }) {
  // A board command starts the whiteboard (the whiteboard CLI does) if it was off.
  const next = { ...board, online: true, saves };
  const step = boardStep(action, name);
  // An older build keeps reporting no view or count, whatever is loaded.
  if (!oldWhiteboard) {
    // Like the whiteboard: under the night view a board waits hidden until it ends.
    if (next.view !== "night") next.view = boardView(step);
    // A loaded save puts its items up; the other board actions keep what is there.
    if (action === "board.load") next.itemCount = BOARD_ITEMS;
    else next.itemCount ??= 0;
  }
  return { board: next, result: boardResult(step, name) };
}
