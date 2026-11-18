// The wizard strip's sections, worked out from its pages: Welcome, Pick,
// Tools (every picked tool's page, with how many are done), Connect (the
// Permissions page) and Summary (the Summary page and the optional Tour page
// after it). A handful of sections instead of a button per page keeps the
// strip to one row with every tool picked, so the page's work starts near the
// top. The tools themselves are listed beside a tool page (ToolList).
import type { SetupTool } from "../../../api";
import type { Screen } from "../wizardScreens";

export type SectionName = "Welcome" | "Pick" | "Tools" | "Connect" | "Summary";

export interface StripSection {
  name: SectionName;
  /** The page a click opens: the section's first page; for Tools, the first unfinished one. */
  target: number;
  isCurrent: boolean;
  /** Tools only: the picked tools that are done, of all of them. */
  count?: { done: number; total: number };
}

const SECTION_OF: Record<Screen["kind"], SectionName> = {
  intro: "Welcome",
  pick: "Pick",
  tool: "Tools",
  permissions: "Connect",
  summary: "Summary",
  tour: "Summary",
};

/** The tool page's tool is done. */
function isToolPageDone(screen: Screen, tools: readonly SetupTool[]): boolean {
  if (screen.kind !== "tool") return false;
  return tools.find((tool) => tool.id === screen.toolId)?.status === "done";
}

/**
 * The strip's sections in order.
 *
 * @param screens The wizard's pages (buildScreens).
 * @param tools The `setup list` answer, for which tools are done.
 * @param at The open page's index.
 * @returns One section per run of pages of the same kind; no Tools while nothing is picked.
 */
export function stripSections(
  screens: readonly Screen[],
  tools: readonly SetupTool[],
  at: number,
): StripSection[] {
  const sections: StripSection[] = [];
  screens.forEach((screen, index) => {
    const name = SECTION_OF[screen.kind];
    const last = sections.at(-1);
    if (last?.name === name) last.isCurrent ||= index === at;
    else sections.push({ name, target: index, isCurrent: index === at });
  });
  const toolPages = screens.flatMap((screen, index) => (screen.kind === "tool" ? [index] : []));
  const toolsSection = sections.find((section) => section.name === "Tools");
  if (toolsSection) {
    const done = toolPages.filter((index) => isToolPageDone(screens[index], tools));
    const unfinished = toolPages.find((index) => !done.includes(index));
    toolsSection.target = unfinished ?? toolPages[0];
    toolsSection.count = { done: done.length, total: toolPages.length };
  }
  return sections;
}
