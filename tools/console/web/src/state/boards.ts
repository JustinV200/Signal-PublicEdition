// Board rows as the UI sees them: rows 0 and 1 are the to-do list and idle board, then one row per
// save, each with the action that puts it on the projector; plus the words
// for what `board.view` says is showing. Shared by the boards view, the
// status line, the scope, the reducer's cursor clamp and the palette.
import type { ActionArgs, ActionName, BoardSave, ServerState } from "../api";

/** Shown wherever the to-do list cannot be requested. */
export const TODO_UNAVAILABLE_REASON = "Not available yet: the whiteboard needs an update";

// The whiteboard's two views (tools/whiteboard's scene model): its own to-do
// list, or the projected items. It never reports which save is loaded.
const TODO_VIEW = "todo";
const ITEMS_VIEW = "items";
const IDLE_VIEW = "idle";

/** One row of the boards view. */
export interface BoardRowInfo {
  name: string;
  description: string | null;
  /** Null for the to-do list, which is not a save. */
  updatedAt: BoardSave["updatedAt"];
  action: ActionName;
  args?: ActionArgs;
  /** Set when the row's button must be off; shown as its tooltip and caption. */
  disabledReason?: string;
  /** The board.update arguments when the board can be redrawn from live data, else null. */
  updateArgs: ActionArgs | null;
}

const TODO_ROW: BoardRowInfo = {
  name: "To-do list",
  description: "The whiteboard's own to-do list.",
  updatedAt: null,
  action: "board.todo",
  updateArgs: { view: "todo" },
};

const IDLE_ROW: BoardRowInfo = {
  name: "Idle board",
  description: "The board's resting view: clock, tasks, weather and news.",
  updatedAt: null,
  action: "board.idle",
  updateArgs: null,
};

/** The board's night view (sleep mode): calibration would light the room. */
export const NIGHT_VIEW = "night";
export const NIGHT_REASON = "Night view is on; calibration would light the room";

/** The rows of the boards view: the to-do list, then the saves in server order. */
export function boardRows(server: ServerState | null): BoardRowInfo[] {
  const saves = server?.board.saves ?? [];
  const available = isTodoAvailable(server);
  const fixed = (row: BoardRowInfo) =>
    available ? row : { ...row, disabledReason: TODO_UNAVAILABLE_REASON };
  return [
    fixed(TODO_ROW),
    fixed(IDLE_ROW),
    ...saves.map((save) => ({
      ...save,
      action: "board.load" as const,
      args: { name: save.name },
      updateArgs: save.refresher ? { name: save.name } : null,
    })),
  ];
}

/** The to-do list and the idle board come before the saves. */
export const FIXED_ROWS = 2;

/** Rows in the boards view: the two fixed rows plus one per save. */
export function boardRowCount(server: ServerState | null): number {
  return FIXED_ROWS + (server?.board.saves.length ?? 0);
}

/**
 * Whether the to-do list and idle board can be requested. Only a whiteboard that is on but
 * reports no `view` (an older build) cannot show it. An off whiteboard can:
 * sending a board starts it through its MCP server.
 */
export function isTodoAvailable(server: ServerState | null): boolean {
  const board = server?.board;
  return !(board?.online && board.view === null);
}

/**
 * Whether `row` is what the projector shows. Only the to-do and idle rows
 * can match: the whiteboard reports `todo`, `idle` or `items`, never which save was loaded.
 */
export function isRowShowing(row: BoardRowInfo, view: string | null): boolean {
  return (
    (row.action === "board.todo" && view === TODO_VIEW) ||
    (row.action === "board.idle" && view === IDLE_VIEW)
  );
}

/** `board.view` in words for the header, tab and scope; `nothing` while there is no view. */
export function boardViewWords(view: string | null): string {
  if (view === TODO_VIEW) return "the to-do list";
  if (view === IDLE_VIEW) return "the idle board";
  if (view === ITEMS_VIEW) return "your board";
  if (view === NIGHT_VIEW) return "the night view";
  return view ?? "nothing";
}
