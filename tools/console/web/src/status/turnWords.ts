// The orchestrator's turn state in words, shared by the status line and the
// scope: `working 0:42 · 5 agents`, `waiting on 5 agents`, `idle`, `no word
// from Claude for 12 min (interrupted?)` or `status unknown until Claude's
// next turn`. Words carry the state everywhere; colour never does alone.
import type { TurnStatus } from "../api";
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
      return `no word from Claude for ${Math.floor(quietMs / MS_PER_MINUTE)} min (interrupted?)`;
    }
    case "unknown":
      return "status unknown until Claude's next turn";
  }
}
