// The fixed command list for Ctrl+K. Every command either calls /api/action
// (through the sender or confirm mode) or changes a local setting; nothing
// else is reachable from here.
import type { ActionArgs, ActionName } from "../api";
import { VIEWS } from "../state";
import type { Theme, View } from "../state";

export interface Command {
  label: string;
  run: () => void;
}

export interface CommandContext {
  /** Names of the saved boards, in server order. */
  saves: readonly string[];
  /** False on an older whiteboard build with no to-do view: the command is left out. */
  todoAvailable: boolean;
  /** The night view is on: realign and calibrate would light the room, so they are left out. */
  nightView: boolean;
  runAction: (action: ActionName, args?: ActionArgs) => void;
  /** Voice actions and a full calibrate go through the y/n line instead of running at once. */
  confirmAction: (action: ActionName) => void;
  setView: (view: View) => void;
  setTheme: (theme: Theme) => void;
}

const THEMES: readonly Theme[] = ["dark", "light"];

/** Builds the palette's commands for the current state. */
export function buildCommands(ctx: CommandContext): Command[] {
  return [
    { label: "voice start", run: () => ctx.confirmAction("voice.start") },
    { label: "voice stop", run: () => ctx.confirmAction("voice.stop") },
    ...ctx.saves.map((name) => ({
      label: `board load ${name}`,
      run: () => ctx.runAction("board.load", { name }),
    })),
    ...(ctx.todoAvailable ? [{ label: "board todo", run: () => ctx.runAction("board.todo") }] : []),
    ...(ctx.todoAvailable ? [{ label: "board idle", run: () => ctx.runAction("board.idle") }] : []),
    ...(ctx.nightView
      ? []
      : [
          { label: "board realign", run: () => ctx.runAction("board.realign") },
          { label: "board calibrate", run: () => ctx.confirmAction("board.calibrate") },
        ]),
    ...VIEWS.map((view) => ({ label: `view ${view}`, run: () => ctx.setView(view) })),
    ...THEMES.map((theme) => ({ label: `theme ${theme}`, run: () => ctx.setTheme(theme) })),
  ];
}
