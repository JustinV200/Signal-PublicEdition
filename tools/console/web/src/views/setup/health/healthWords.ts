// How a health row reads, for the tools (`setup status --json`) and the
// console's own checks (GET /api/health): a mark and a label for each state,
// so the state never rides on colour alone (it also works for colourblind
// users), the check's words, its fix and command, and a tool's button. A
// finished tool that isn't in Claude Code's config yet (`wired` false) reads
// as its own state, never Active: Claude Code can't use it until it's added.
import type { CheckLevel, ConsoleCheck, HealthState, ToolHealth } from "../../../api";
import type { MarkShape } from "../../../ui";
import { ADD_TO_CLAUDE } from "../run";

/** What a tool row shows: the CLI's state, or `not_wired` for a finished tool not added yet. */
export type ShownHealth = HealthState | "not_wired";

/** The row's colour class; it only repeats what the mark and label say. */
export type HealthTone = "ok" | "attention" | "bad" | "off";

export interface HealthLook {
  /** A ui `Mark` shape that differs per state: disc, half, cross, ring. */
  mark: MarkShape;
  label: string;
}

/** One row of a health list, whichever check it came from. */
export interface HealthItem {
  /** Unique on the page, e.g. `console-turn-hook`; the row's element id is healthRowId(key). */
  key: string;
  name: string;
  look: HealthLook;
  tone: HealthTone;
  /** What the check found, in words ("" when it said nothing). */
  words: string;
  /** Faint words after them, e.g. a tool's platform; "" for none. */
  note: string;
  /** What to do, and the command that does it; "" for none. */
  fix: string;
  command: string;
}

/** A finished tool not in Claude Code's config yet; its tool page's banner reads the same. */
export const NOT_WIRED_LOOK: HealthLook = {
  mark: "half",
  label: "Set up, not added to Claude Code yet",
};

const TOOL_LOOKS: Record<ShownHealth, HealthLook & { tone: HealthTone }> = {
  active: { mark: "disc", label: "Active", tone: "ok" },
  not_wired: { ...NOT_WIRED_LOOK, tone: "attention" },
  down: { mark: "cross", label: "Down", tone: "bad" },
  not_set_up: { mark: "ring", label: "Not set up", tone: "off" },
};

// Same shapes as the tools: a half disc needs a look, a cross is broken.
const CONSOLE_LOOKS: Record<CheckLevel, HealthLook & { tone: HealthTone }> = {
  ok: { mark: "disc", label: "OK", tone: "ok" },
  attention: { mark: "half", label: "Needs a look", tone: "attention" },
  fail: { mark: "cross", label: "Not working", tone: "bad" },
};

/** The state a row shows: a finished tool that isn't wired is `not_wired`, whatever its check said. */
export function shownHealth(row: ToolHealth): ShownHealth {
  return row.state !== "not_set_up" && !row.wired ? "not_wired" : row.state;
}

/** The mark and label for a tool row. */
export function healthLook(row: ToolHealth): HealthLook {
  const { mark, label } = TOOL_LOOKS[shownHealth(row)];
  return { mark, label };
}

/** The element id of a health row, so another group (Models) can point at it. */
export function healthRowId(key: string): string {
  return `health-${key}`;
}

/** A tool's row: its state, the check's words, fix and command, and its platform. */
export function toolItem(row: ToolHealth): HealthItem {
  const { tone, ...look } = TOOL_LOOKS[shownHealth(row)];
  const { words, fix, command } = row;
  return {
    key: `tool-${row.id}`,
    name: row.name,
    look,
    tone,
    words,
    note: row.platform,
    fix,
    command,
  };
}

/** One of the console's own checks as a row (its fix and command come only when it's not ok). */
export function consoleItem(check: ConsoleCheck): HealthItem {
  const { tone, ...look } = CONSOLE_LOOKS[check.level];
  const { name, words, fix, command } = check;
  return { key: consoleRowKey(check.id), name, look, tone, words, note: "", fix, command };
}

/** The row key of a console check, e.g. `console-session-hook`. */
export function consoleRowKey(checkId: string): string {
  return `console-${checkId}`;
}

/** The row's button: Add to Claude Code, Fix when down, Re-run setup when active, else Set up (or Continue). */
export function healthAction(row: ToolHealth): string {
  const shown = shownHealth(row);
  if (shown === "not_wired") return ADD_TO_CLAUDE;
  if (shown === "down") return "Fix";
  if (shown === "active") return "Re-run setup";
  return row.setupStatus === "started" || row.setupStatus === "failed"
    ? "Continue setup"
    : "Set up";
}

/** `3 active · 1 not added to Claude Code · 1 down · 9 not set up` for a header (no zero "not added"). */
export function healthCounts(rows: readonly ToolHealth[]): string {
  const count = (state: ShownHealth) => rows.filter((row) => shownHealth(row) === state).length;
  const notAdded = count("not_wired");
  return [
    `${count("active")} active`,
    ...(notAdded > 0 ? [`${notAdded} not added to Claude Code`] : []),
    `${count("down")} down`,
    `${count("not_set_up")} not set up`,
  ].join(" · ");
}

/** `11 ok · 1 needs a look · 0 not working` for the Console group's header. */
export function checkCounts(checks: readonly ConsoleCheck[]): string {
  const count = (level: CheckLevel) => checks.filter((check) => check.level === level).length;
  return `${count("ok")} ok · ${count("attention")} needs a look · ${count("fail")} not working`;
}
