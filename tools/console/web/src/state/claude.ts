// Whether the console has a Claude Code session to send to: never claimed,
// claimed but that session has closed, or linked. The status line, Chat, the
// input line, the scope and the setup hand-off all read it from here, so they
// never disagree about it.
import type { OrchestratorState, ServerState } from "../api";

/** `none`: no session ever claimed the console; `closed`: the claimed one is gone; `linked`: it is open. */
export type ClaudeLink = "none" | "closed" | "linked";

/** What the owner pastes into Claude Code to link that session to the console. */
export const CLAIM_SENTENCE =
  "Run this with your Bash tool: uv run --project tools/console --frozen --no-sync console claim";

/** The note after a copy of something to paste into Claude Code (the claim sentence, a hand-off). */
export const PASTE_INTO_CLAUDE_NOTE = "Copied. Paste it into Claude Code in this folder.";

const NO_SESSION_REASON = "no Claude session yet";
const CLOSED_REASON = "Claude session closed";

/** The link state of the server's orchestrator block. */
export function claudeLink(orchestrator: OrchestratorState): ClaudeLink {
  if (!orchestrator.claimed) return "none";
  return orchestrator.alive ? "linked" : "closed";
}

/** Why a typed message can't go to Claude now; undefined when it can, or before the first snapshot. */
export function sendBlockedReason(server: ServerState | null): string | undefined {
  if (!server) return undefined;
  const link = claudeLink(server.orchestrator);
  if (link === "none") return NO_SESSION_REASON;
  if (link === "closed") return CLOSED_REASON;
  return undefined;
}
