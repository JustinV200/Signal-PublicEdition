// The wizard's screens (shown as "pages") and where it resumes. The page the
// owner is on is kept in the store by its key (screenKey), so leaving Setup
// and coming back lands on it again; nothing is saved past the page load, so a
// new window lands on the first unfinished tool, worked out from the setup
// CLI's progress (`setup list`).
import type { SetupTool } from "../../api";

export type Screen =
  | { kind: "intro" }
  | { kind: "pick" }
  | { kind: "tool"; toolId: string }
  | { kind: "permissions" }
  | { kind: "summary" }
  | { kind: "tour" };

/** The Task console's registry id: pre-ticked on a first run, and home of the claim step. */
export const CONSOLE_ID = "console";

/**
 * The tool is among the picks (`setup list`'s `picked`, from `setup choose`). Not its
 * status: the setup window builds the console before anything is picked, so a done
 * console on a fresh checkout is not a pick.
 */
export function isChosen(tool: SetupTool): boolean {
  return tool.picked;
}

/** The ticks Pick tools opens with: the picks, or before any pick just the Task console. */
export function initialPicks(tools: readonly SetupTool[]): Set<string> {
  const picked = tools.filter(isChosen).map((tool) => tool.id);
  if (picked.length > 0) return new Set(picked);
  return new Set(tools.some((tool) => tool.id === CONSOLE_ID) ? [CONSOLE_ID] : []);
}

/** Intro, picks, one screen per picked tool, permissions, summary, then the optional tour. */
export function buildScreens(tools: readonly SetupTool[]): Screen[] {
  return [
    { kind: "intro" },
    { kind: "pick" },
    ...tools.filter(isChosen).map((tool): Screen => ({ kind: "tool", toolId: tool.id })),
    { kind: "permissions" },
    { kind: "summary" },
    { kind: "tour" },
  ];
}

/**
 * Where the wizard opens: `toolId`'s screen when asked for (and picked),
 * else the intro on a first run, else the first picked tool not done yet,
 * else (everything picked is done) the summary; the tour stays an optional
 * screen after it.
 */
export function resumeIndex(
  screens: readonly Screen[],
  tools: readonly SetupTool[],
  toolId: string | null,
): number {
  const toolIndex = (id: string) =>
    screens.findIndex((screen) => screen.kind === "tool" && screen.toolId === id);
  if (toolId && toolIndex(toolId) >= 0) return toolIndex(toolId);
  if (!tools.some(isChosen)) return 0;
  const unfinished = firstUnfinishedPick(tools);
  if (unfinished) return toolIndex(unfinished.id);
  return screens.findIndex((screen) => screen.kind === "summary");
}

/**
 * The open page: the kept one (`keptKey`, a screenKey) while it still exists,
 * else where setup stopped (resumeIndex). A kept page wins even after its tool
 * turns done, so finishing a step never moves the wizard.
 */
export function openIndex(
  screens: readonly Screen[],
  tools: readonly SetupTool[],
  toolId: string | null,
  keptKey: string | null,
): number {
  const kept = screens.findIndex((screen) => screenKey(screen) === keptKey);
  return kept >= 0 ? kept : resumeIndex(screens, tools, toolId);
}

/**
 * The page key to write to the store, or null to leave it: the open page, once
 * it differs from the kept one, so a later `setup list` can't move the wizard.
 * Not while a pick runs (the asked-for tool's page is on its way).
 */
export function pageToKeep(
  openKey: string | null,
  keptKey: string | null,
  needsPick: boolean,
): string | null {
  return openKey !== null && !needsPick && openKey !== keptKey ? openKey : null;
}

/** The first picked tool that isn't done; undefined when every pick is done (or none). */
function firstUnfinishedPick(tools: readonly SetupTool[]): SetupTool | undefined {
  return tools.filter(isChosen).find((tool) => tool.status !== "done");
}

/**
 * Whether the status line shows a Setup tab: while Setup is open, or while a
 * picked tool is unfinished. `tools` is null while the picks are not read yet,
 * or the first read failed (a later failure keeps the last answer): that hides
 * the tab; System's `Open setup` and Ctrl+9 still reach Setup.
 */
export function showsSetupTab(isSetupOpen: boolean, tools: readonly SetupTool[] | null): boolean {
  return isSetupOpen || (tools !== null && firstUnfinishedPick(tools) !== undefined);
}

/** A screen's key, stable while the picks change: its kind, or `tool:<id>`. */
export function screenKey(screen: Screen): string {
  return screen.kind === "tool" ? `tool:${screen.toolId}` : screen.kind;
}

/** A screen's name, the page's title. */
export function screenName(screen: Screen, tools: readonly SetupTool[]): string {
  if (screen.kind === "tool")
    return tools.find((t) => t.id === screen.toolId)?.name ?? screen.toolId;
  const names = {
    intro: "Welcome",
    pick: "Pick tools",
    permissions: "Permissions",
    summary: "Summary",
    tour: "Tour",
  };
  return names[screen.kind];
}
