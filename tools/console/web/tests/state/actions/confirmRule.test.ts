// One confirm rule for the buttons and the palette: only a full calibrate, and
// loading a save or showing a `tasks` save's live version over a drawing, ask
// first. The to-do list, the idle board, a `todo` save's live version,
// realign and voice run at once, and an empty `items` view wipes nothing, so it
// does not ask.
import { describe, expect, it } from "vitest";
import type { ActionArgs, ActionName, BoardState } from "../../../src/api";
import { confirmPrompt } from "../../../src/state";

const REPLACE = 'Replace what is on the projector with "lecture"? Anything unsaved there is lost.';
const CALIBRATE = "Flash calibration markers on the projector?";
const LECTURE: ActionArgs = { name: "lecture" };
const WEEK: ActionArgs = { name: "week" };

// "lecture" redraws from the live tasks (clears the board); "week" is a to-do list view switch.
const SAVES: BoardState["saves"] = [
  { name: "lecture", updatedAt: null, description: null, refresher: "tasks" },
  { name: "week", updatedAt: null, description: null, refresher: "todo" },
];

function board(view: string | null, itemCount: number | null = null): BoardState {
  return { saves: SAVES, view, itemCount, online: true };
}

describe("confirmPrompt", () => {
  it.each<[string, ActionName, ActionArgs | undefined, BoardState | undefined, string | null]>([
    ["load over a drawing", "board.load", LECTURE, board("items", 3), REPLACE],
    ["load over items of unknown count", "board.load", LECTURE, board("items"), REPLACE],
    ["load over an empty items view", "board.load", LECTURE, board("items", 0), null],
    ["load over the to-do list", "board.load", LECTURE, board("todo"), null],
    ["load over the idle board", "board.load", LECTURE, board("idle"), null],
    ["load with the whiteboard off", "board.load", LECTURE, undefined, null],
    ["to-do list over a drawing", "board.todo", undefined, board("items", 3), null],
    ["idle board over a drawing", "board.idle", undefined, board("items", 3), null],
    ["tasks redraw over a drawing", "board.update", LECTURE, board("items", 3), REPLACE],
    ["to-do redraw over a drawing", "board.update", WEEK, board("items", 3), null],
    ["realign", "board.realign", undefined, board("items", 3), null],
    ["full calibrate", "board.calibrate", undefined, board("todo"), CALIBRATE],
    ["voice start", "voice.start", undefined, board("items", 3), null],
    ["voice stop", "voice.stop", undefined, board("items", 3), null],
  ])("%s", (_case, action, args, state, expected) => {
    expect(confirmPrompt(action, args, state)).toBe(expected);
  });
});
