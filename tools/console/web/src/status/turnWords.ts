// The orchestrator's turn state in words, shared by the status line (behind
// `Claude · `) and the scope: `working 0:42 · 5 agents`, `waiting on 5
// agents`, `idle`, `quiet for 12 min (interrupted?)` or `state unknown until
// its next turn`. Words carry the state everywhere; colour never does alone.
// turnCauseWords adds the cause from the console's health checks, so the
// status line and the scope say the same: `state unknown · turn hook missing`
// while the Turn hook check fails.
import { TURN_HOOK_CHECK } from "../api";
import type { ConsoleCheck, TurnStatus } from "../api";
import { formatElapsed } from "../time";

const MS_PER_MINUTE = 60 * 1000;

/** `5 agents`, `1 agent`, or `2? agents` when the two counts disagree. */
function agentWords(turn: TurnStatus): string {
  const count = turn.agents ?? 0;
  return `${count}${turn.agentsUnsure ? "?" : ""} ${count === 1 ? "agent" : "agents"}`;
}

/** The turn state as a short phrase at `now` (epoch ms). */
export function turnWords(turn: TurnStatus, now: number): string {
  switch (turn.state) {
    case "working": {
      const clock = formatElapsed(now - (turn.startedAt ?? now));
      return turn.agents ? `working ${clock} · ${agentWords(turn)}` : `working ${clock}`;
    }
    case "agents":
      return `waiting on ${agentWords(turn)}`;
    case "idle":
      return "idle";
    case "stale": {
      const quietMs = now - (turn.lastActivityAt ?? now);
      return `quiet for ${Math.floor(quietMs / MS_PER_MINUTE)} min (interrupted?)`;
    }
    case "unknown":
      return "state unknown until its next turn";
  }
}

/** `unknown`'s words when the turn hook is missing: no turn can ever be reported. */
export const HOOK_MISSING_WORDS = "state unknown · turn hook missing";

/** The Turn hook check while it fails (missing or partly missing), else null. */
export function failingTurnHook(checks: readonly ConsoleCheck[] | null): ConsoleCheck | null {
  return checks?.find((check) => check.id === TURN_HOOK_CHECK && check.level === "fail") ?? null;
}

/**
 * turnWords, with `state unknown`'s cause from the console's checks: a failing
 * Turn hook check reads HOOK_MISSING_WORDS; anything else (no turn yet, or the
 * checks not read yet) waits for the next turn.
 */
export function turnCauseWords(
  turn: TurnStatus,
  checks: readonly ConsoleCheck[] | null,
  now: number,
): string {
  if (turn.state === "unknown" && failingTurnHook(checks)) return HOOK_MISSING_WORDS;
  return turnWords(turn, now);
}
