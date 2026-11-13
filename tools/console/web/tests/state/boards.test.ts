// The to-do row's button is off, with the reason the UI shows, only when the
// whiteboard is on but reports no view (an older build). An off whiteboard
// keeps it on, because sending a board starts the whiteboard. Only the to-do
// row can ever be "showing": the whiteboard never names the loaded save.
import { describe, expect, it } from "vitest";
import type { BoardState, ServerState } from "../../src/api";
import { boardRows, isRowShowing, isTodoAvailable, TODO_UNAVAILABLE_REASON } from "../../src/state";

function server(board: Pick<BoardState, "view" | "online">): ServerState {
  return {
    orchestrator: {
      claimed: true,
      label: "main",
      turn: {
        state: "idle",
        startedAt: null,
        lastActivityAt: null,
        agents: 0,
        agentsUnsure: false,
      },
    },
    voice: { running: false, phase: null, startedBy: null },
    board: {
      saves: [
        { name: "todo", updatedAt: null, description: null, refresher: null },
        { name: "grid", updatedAt: null, description: null, refresher: "tasks" },
      ],
      ...board,
    },
    models: null,
  };
}

describe("boardRows", () => {
  it("disables the to-do row with a reason when the whiteboard is on but reports no view", () => {
    const [todo, idle, save] = boardRows(server({ online: true, view: null }));
    expect(todo).toMatchObject({ action: "board.todo", disabledReason: TODO_UNAVAILABLE_REASON });
    expect(idle).toMatchObject({ action: "board.idle", disabledReason: TODO_UNAVAILABLE_REASON });
    expect(save).toMatchObject({ action: "board.load", args: { name: "todo" } });
    expect(save.disabledReason).toBeUndefined();
    // Update shows only where something can redraw the board: a refresher, or the to-do list.
    expect([todo.updateArgs, idle.updateArgs, save.updateArgs]).toEqual([
      { view: "todo" },
      null,
      null,
    ]);
    expect(boardRows(server({ online: true, view: "items" }))[3].updateArgs).toEqual({
      name: "grid",
    });
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
