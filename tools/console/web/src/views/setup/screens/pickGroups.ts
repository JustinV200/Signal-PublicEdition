// Pick tools' grouping and words: the registry's groups in a fixed order (a
// tool with no known group goes under Extras), and the Save button's label in
// the singular for one pick.
import type { SetupTool } from "../../../api";

/** The Pick page's groups, in the order they show. */
export const PICK_GROUPS = ["Core", "Everyday", "Hardware", "Extras"] as const;
const FALLBACK_GROUP = "Extras";

/** Each group that has a tool, with its tools in registry order. */
export function groupTools(tools: readonly SetupTool[]): { name: string; tools: SetupTool[] }[] {
  const groupOf = (tool: SetupTool) =>
    (PICK_GROUPS as readonly string[]).includes(tool.group) ? tool.group : FALLBACK_GROUP;
  return PICK_GROUPS.map((name) => ({
    name,
    tools: tools.filter((tool) => groupOf(tool) === name),
  })).filter((group) => group.tools.length > 0);
}

/** "Save 1 pick and install", "Save 3 picks and install". */
export function saveLabel(count: number): string {
  return `Save ${count} ${count === 1 ? "pick" : "picks"} and install`;
}
