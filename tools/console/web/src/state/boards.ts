// Board rows as the UI sees them: rows 0 and 1 are the to-do list and idle
// board, then one row per save, each with the action that puts it on the
// projector and a key that names it across snapshots; the preview's buttons per
// row; plus the words for what `board.view` says is showing and whether a
// drawing is up. Shared by the boards view, the status line, the scope, the
// reducer's selection, the confirm rule and the palette.
import type { ActionArgs, ActionName, BoardSave, BoardState, ServerState } from "../api";

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
  /**
   * The board.update arguments for a save that can be redrawn from live data (it has a
   * refresher), else null. The to-do list has none: sending it already redraws it.
   */
  updateArgs: ActionArgs | null;
  /** What redraws a save from live data (`tasks`, `todo`); null for the fixed rows. */
  refresher: BoardSave["refresher"];
}

/** One button in a board's preview: its label and the action it runs. */
export interface BoardButton {
  label: string;
  action: ActionName;
  args?: ActionArgs;
  /** The preview's one primary button. */
  primary: boolean;
}

const TODO_ROW: BoardRowInfo = {
  name: "To-do list",
  description: "The whiteboard's own to-do list.",
  updatedAt: null,
  action: "board.todo",
  updateArgs: null,
  refresher: null,
};

const IDLE_ROW: BoardRowInfo = {
  name: "Idle board",
  description: "The whiteboard's resting view: clock, tasks, weather and news.",
  updatedAt: null,
  action: "board.idle",
  updateArgs: null,
  refresher: null,
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

/**
 * The preview's buttons for `row`, primary first. A save with live data leads with
 * `Show live version` (board.update: redraws it from live data and shows it), since
 * its saved copy is stale; `Show saved copy` loads that copy. Every other row has
 * one `Send to projector`.
 */
export function boardButtons(row: BoardRowInfo): BoardButton[] {
  const send = { action: row.action, args: row.args };
  if (!row.updateArgs) return [{ label: "Send to projector", primary: true, ...send }];
  return [
    { label: "Show live version", action: "board.update", args: row.updateArgs, primary: true },
    { label: "Show saved copy", primary: false, ...send },
  ];
}

/**
 * A row's name across snapshots (`action:name`). The selection stores this, not
 * a row number, because a new save arriving at the top moves every row down.
 */
export function boardRowKey(row: BoardRowInfo): string {
  return `${row.action}:${row.name}`;
}

/** The to-do row's key: where the selection starts and where it falls back. */
export const TODO_ROW_KEY = boardRowKey(TODO_ROW);

/** Index of the row named `key`; the to-do row (0) when that board is gone. */
export function boardIndexOf(rows: readonly BoardRowInfo[], key: string): number {
  return Math.max(
    0,
    rows.findIndex((row) => boardRowKey(row) === key),
  );
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

/**
 * Whether the projector may hold a drawing (unsaved items) that loading a save
 * would wipe: the view is `items` and the whiteboard has not said it is empty.
 * An unknown count counts as a drawing, so the confirm errs on asking.
 */
export function isDrawingUp(board: BoardState | undefined): boolean {
  return board?.view === ITEMS_VIEW && board.itemCount !== 0;
}

/** `board.view` in words for the header and scope; `nothing` while there is no view. */
export function boardViewWords(view: string | null): string {
  if (view === TODO_VIEW) return "the to-do list";
  if (view === IDLE_VIEW) return "the idle board";
  if (view === ITEMS_VIEW) return "a drawing";
  if (view === NIGHT_VIEW) return "the night view";
  return view ?? "nothing";
}

// The Boards tab's short words: what is up, kept brief so all tabs fit one row.
const TAB_WORDS: Record<string, string> = {
  [TODO_VIEW]: "to-do list",
  [IDLE_VIEW]: "idle",
  [ITEMS_VIEW]: "drawing",
  [NIGHT_VIEW]: "night",
};

/**
 * The Boards tab's words for `board`: `to-do list`, `idle`, `drawing`, `night` or `off`.
 * An older whiteboard that is on but reports no view reads `on`.
 */
export function boardTabWords(board: BoardState | undefined): string {
  if (!board?.online) return "off";
  if (board.view === null) return "on";
  // hasOwn, not `??`: a view named like an Object.prototype key must not read its member.
  return Object.hasOwn(TAB_WORDS, board.view) ? TAB_WORDS[board.view] : board.view;
}
