// The Commands list: the buttons' words, fixed commands first and saved boards
// last, only the command that applies now (voice, away, theme, the open view,
// the whiteboard's state), and a word filter that finds commands by any of
// their words in any order.
import { describe, expect, it } from "vitest";
import { buildCommands, filterCommands } from "../../src/palette";
import type { CommandContext } from "../../src/palette";

const NOOP = () => {};

const BASE: CommandContext = {
  saves: ["lecture", "lab 2"],
  todoAvailable: true,
  nightView: false,
  voiceRunning: false,
  away: "here",
  theme: "dark",
  view: "scope",
  runAction: NOOP,
  setView: NOOP,
  setTheme: NOOP,
  setAway: NOOP,
  openHelp: NOOP,
  refresh: NOOP,
};

const FULL_LIST = [
  "Start voice",
  "Send to projector: to-do list",
  "Send to projector: idle board",
  "Realign whiteboard",
  "Full calibrate",
  "Go to Chat",
  "Go to Voice",
  "Go to Boards",
  "Go to Tasks",
  "Go to System",
  "Open setup",
  "Light theme",
  "I'm away",
  "Help",
  "Refresh",
  'Send to projector: "lecture"',
  'Send to projector: "lab 2"',
];

describe("Commands", () => {
  it.each<[string, Partial<CommandContext>, string, string[]]>([
    ["everything, in order", {}, "", FULL_LIST],
    ["voice running", { voiceRunning: true }, "voice", ["Stop voice", "Go to Voice"]],
    ["away", { away: "away" }, "i'm", ["I'm back"]],
    ["asleep: sleep mode decides", { away: "asleep" }, "away", []],
    ["light theme", { theme: "light" }, "theme", ["Dark theme"]],
    ["on Setup", { view: "setup" }, "setup", []],
    [
      "night view: no realign or calibrate",
      { nightView: true },
      "",
      FULL_LIST.filter((label) => label !== "Realign whiteboard" && label !== "Full calibrate"),
    ],
    ["send", {}, "send", FULL_LIST.filter((label) => label.startsWith("Send to projector"))],
    ["projector, any word order", {}, "lecture projector", ['Send to projector: "lecture"']],
    ["to-do", {}, "to-do", ["Send to projector: to-do list"]],
    ["typed without the apostrophe", {}, "im away", ["I'm away"]],
  ])("%s: %j finds the right ones", (_, overrides, query, expected) => {
    const commands = buildCommands({ ...BASE, ...overrides });
    expect(filterCommands(commands, query).map((command) => command.label)).toEqual(expected);
  });
});
