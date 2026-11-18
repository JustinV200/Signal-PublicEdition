// The Commands list for Ctrl+K, in the buttons' words. Every command either
// calls /api/action (through the confirm gate, like the buttons), sets away
// mode (like System's YOU buttons), changes a local setting, opens help or
// re-reads the state; nothing else is reachable from here. Only the commands
// that apply now are listed: the fixed ones first, the saved boards last.
import type { ActionArgs, ActionName, AwayState } from "../api";
import { actionLabel, VIEWS } from "../state";
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
  /** Voice runs (or is starting): `Stop voice` instead of `Start voice`. */
  voiceRunning: boolean;
  /** The owner's away mode; null while unreadable, which offers neither away command. */
  away: AwayState | null;
  /** The theme on the page now: only the other one is offered. */
  theme: Theme;
  /** The open view: its own `Go to` is left out. */
  view: View;
  /** Runs an action, asking first where the confirm rule says so (the buttons' gate). */
  runAction: (action: ActionName, args?: ActionArgs) => void;
  setView: (view: View) => void;
  setTheme: (theme: Theme) => void;
  /** Turns away mode on (for the brief's default 3 days) or off, like System's YOU buttons. */
  setAway: (isAway: boolean) => void;
  openHelp: () => void;
  /** Re-reads everything now, like the status line's Refresh (which shows only when stale or offline). */
  refresh: () => void;
}

/** `Go to System` for a view; Setup reads `Open setup`, like System's button. */
function viewCommandLabel(view: View): string {
  if (view === "setup") return "Open setup";
  return `Go to ${view[0].toUpperCase()}${view.slice(1)}`;
}

/** `Light theme` while dark, `Dark theme` while light. */
function themeCommand(ctx: CommandContext): Command {
  const other: Theme = ctx.theme === "dark" ? "light" : "dark";
  const label = other === "light" ? "Light theme" : "Dark theme";
  return { label, run: () => ctx.setTheme(other) };
}

/** `I'm away` while here, `I'm back` while away; none while asleep (sleep mode decides) or unknown. */
function awayCommands(ctx: CommandContext): Command[] {
  if (ctx.away === "here") return [{ label: "I'm away", run: () => ctx.setAway(true) }];
  if (ctx.away === "away") return [{ label: "I'm back", run: () => ctx.setAway(false) }];
  return [];
}

/** A command that runs `action`, labelled like the row it leaves (`actionLabel`). */
function actionCommand(ctx: CommandContext, action: ActionName, args?: ActionArgs): Command {
  return { label: actionLabel(action, args), run: () => ctx.runAction(action, args) };
}

/** The whiteboard's fixed commands: to-do list, idle board, realign and calibrate, where they apply. */
function boardCommands(ctx: CommandContext): Command[] {
  const views = ctx.todoAvailable
    ? [actionCommand(ctx, "board.todo"), actionCommand(ctx, "board.idle")]
    : [];
  const calibration = ctx.nightView
    ? []
    : [actionCommand(ctx, "board.realign"), actionCommand(ctx, "board.calibrate")];
  return [...views, ...calibration];
}

/** Builds the palette's commands for the current state. */
export function buildCommands(ctx: CommandContext): Command[] {
  return [
    actionCommand(ctx, ctx.voiceRunning ? "voice.stop" : "voice.start"),
    ...boardCommands(ctx),
    ...VIEWS.filter((view) => view !== ctx.view).map((view) => ({
      label: viewCommandLabel(view),
      run: () => ctx.setView(view),
    })),
    themeCommand(ctx),
    ...awayCommands(ctx),
    { label: "Help", run: ctx.openHelp },
    { label: "Refresh", run: ctx.refresh },
    // Saved boards last: there can be many, and the fixed commands stay near the top.
    ...ctx.saves.map((name) => actionCommand(ctx, "board.load", { name })),
  ];
}
