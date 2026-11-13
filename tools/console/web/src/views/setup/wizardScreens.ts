// The wizard's screens and where it resumes. Nothing about the wizard's place
// is stored: it's worked out from the setup CLI's progress (`setup list`), so
// closing the window and opening it again lands on the first unfinished tool.
import type { SetupTool } from "../../api";

export type Screen =
  | { kind: "intro" }
  | { kind: "pick" }
  | { kind: "tool"; toolId: string }
  | { kind: "permissions" }
  | { kind: "summary" }
  | { kind: "tour" };

// `setup list` statuses that mean the tool isn't among the picks.
const NOT_PICKED = new Set(["skipped", "not set up"]);

/** The tool is among the picks (`setup choose` un-skips it; never-touched tools are not). */
export function isChosen(tool: SetupTool): boolean {
  return !NOT_PICKED.has(tool.status);
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
  const chosen = tools.filter(isChosen);
  if (chosen.length === 0) return 0;
  const unfinished = chosen.find((tool) => tool.status !== "done");
  if (unfinished) return toolIndex(unfinished.id);
  return screens.findIndex((screen) => screen.kind === "summary");
}

/** A screen's short name for the progress strip. */
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
