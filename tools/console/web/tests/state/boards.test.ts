// The to-do row's button is off, with the reason the UI shows, only when the
// whiteboard is on but reports no view (an older build). An off whiteboard
// keeps it on, because sending a board starts the whiteboard. Only the to-do
// row can ever be "showing": the whiteboard never names the loaded save. Each
// row kind gets its preview buttons: one primary each, and a save drawn from
// live data leads with its live version.
import { describe, expect, it } from "vitest";
import type { BoardState, ServerState } from "../../src/api";
import {
  boardButtons,
  boardRows,
  isRowShowing,
  isTodoAvailable,
  TODO_UNAVAILABLE_REASON,
} from "../../src/state";
import { serverState } from "./serverFixture";

function server(board: Pick<BoardState, "view" | "online">): ServerState {
  return serverState({
    saves: [
      { name: "todo", updatedAt: null, description: null, refresher: null },
      { name: "grid", updatedAt: null, description: null, refresher: "tasks" },
    ],
    ...board,
  });
}

describe("boardRows", () => {
  it("disables the to-do row with a reason when the whiteboard is on but reports no view", () => {
    const [todo, idle, save] = boardRows(server({ online: true, view: null }));
    expect(todo).toMatchObject({ action: "board.todo", disabledReason: TODO_UNAVAILABLE_REASON });
    expect(idle).toMatchObject({ action: "board.idle", disabledReason: TODO_UNAVAILABLE_REASON });
    expect(save).toMatchObject({ action: "board.load", args: { name: "todo" } });
    expect(save.disabledReason).toBeUndefined();
    expect(isTodoAvailable(server({ online: true, view: "items" }))).toBe(true);
  });

  it("keeps the to-do row enabled while the whiteboard is off", () => {
    const [todo] = boardRows(server({ online: false, view: null }));
    expect(todo.disabledReason).toBeUndefined();
    expect(isTodoAvailable(null)).toBe(true);
  });

  it("marks only the to-do and idle rows as showing, even beside a save named todo", () => {
    const [todo, idle, save] = boardRows(server({ online: true, view: "todo" }));
    expect(isRowShowing(todo, "todo")).toBe(true);
    expect(isRowShowing(idle, "idle")).toBe(true);
    expect(isRowShowing(idle, "todo")).toBe(false);
    expect(isRowShowing(save, "todo")).toBe(false);
    expect(isRowShowing(todo, "items")).toBe(false);
  });
});

describe("boardButtons", () => {
  // Row index in boardRows: 0 to-do list, 1 idle board, 2 a plain save, 3 a save with live data.
  it.each([
    ["the to-do list", 0, [["Send to projector", "board.todo", undefined, true]]],
    ["the idle board", 1, [["Send to projector", "board.idle", undefined, true]]],
    ["a plain save", 2, [["Send to projector", "board.load", { name: "todo" }, true]]],
    [
      "a save with live data",
      3,
      [
        ["Show live version", "board.update", { name: "grid" }, true],
        ["Show saved copy", "board.load", { name: "grid" }, false],
      ],
    ],
  ])("gives %s its buttons, one primary", (_kind, index, expected) => {
    const row = boardRows(server({ online: true, view: "items" }))[index];
    const buttons = boardButtons(row).map((b) => [b.label, b.action, b.args, b.primary]);
    expect(buttons).toEqual(expected);
  });
});
