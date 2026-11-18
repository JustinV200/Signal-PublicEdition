// Word filter for the command palette: every typed word must appear in the
// label, in any order, so `send lecture` finds `Send to projector: "lecture"`.
import type { Command } from "./commands";

// Left out on both sides, so `im away` finds `I'm away` and `todo` finds `to-do list`.
const IGNORED_MARKS = /['’"-]/g;

/** Lower case without the marks people skip when typing. */
function normalise(text: string): string {
  return text.toLowerCase().replace(IGNORED_MARKS, "");
}

/** The commands whose label holds every word of `query` (case-insensitive), in list order. */
export function filterCommands(commands: readonly Command[], query: string): Command[] {
  const words = normalise(query).split(/\s+/).filter(Boolean);
  return commands.filter((command) => {
    const label = normalise(command.label);
    return words.every((word) => label.includes(word));
  });
}
