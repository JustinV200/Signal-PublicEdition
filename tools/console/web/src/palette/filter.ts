// Substring filter for the command palette.
import type { Command } from "./commands";

const MAX_MATCHES = 8;

/** Commands whose label contains `query` (case-insensitive), first `MAX_MATCHES` only. */
export function filterCommands(commands: readonly Command[], query: string): Command[] {
  const needle = query.trim().toLowerCase();
  return commands
    .filter((command) => command.label.toLowerCase().includes(needle))
    .slice(0, MAX_MATCHES);
}
