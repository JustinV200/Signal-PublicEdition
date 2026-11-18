// The status line's connection words: what the page knows about the console
// server and the Claude session, as parts joined by a faint `·`. Each state
// reads differently, so server down, never claimed and a closed session can't
// be mistaken for one another, and every warning is worded, not just coloured.
// `spoken` is the same without clocks or counts, for the live region: it
// changes only when the state does, so a screen reader doesn't re-read the
// line every second. `state unknown` takes its cause from the console's
// health checks: a missing turn hook reads as such, else it waits for a turn.
import type { OrchestratorState, TurnStateName } from "../api";
import { claudeLink } from "../state";
import type { AppState } from "../state";
import { formatRelative, toMs } from "../time";
import { failingTurnHook, HOOK_MISSING_WORDS, turnWords } from "./turnWords";

const MS_PER_SECOND = 1000;
const FIX_HINT = "Chat has the sentence to paste into Claude Code, with Copy.";
const OFFLINE_WORDS = "Console server not answering";
const HOOK_MISSING_FIX = "System's Console group has the fix and its command.";
/** Each turn state as spoken: no clock, no agent count. */
const SPOKEN_TURN: Record<TurnStateName, string> = {
  working: "working",
  agents: "waiting on agents",
  idle: "idle",
  stale: "quiet (interrupted?)",
  unknown: "state unknown until its next turn",
};

export interface ConnectionWords {
  /** Changes when the wording changes (not on every clock tick). */
  key: string;
  /** Shown joined by a faint `·`. */
  parts: string[];
  /** The full words, then the session's label and claim age, or the fix: the tooltip. */
  title: string;
  /** The words for the live region: the state only, with no clock or count in it. */
  spoken: string;
  /** Warning style (also worded, never colour alone). */
  warn: boolean;
}

/** The words, spoken as shown; the states with a clock or a count override `spoken`. */
function words(key: string, parts: string[], detail: string[], warn = false): ConnectionWords {
  const text = parts.join(" · ");
  return { key, parts, title: [text, ...detail.filter(Boolean)].join("\n"), spoken: text, warn };
}

/**
 * `Session: main, linked 3d ago`; `Session linked 3d ago` unlabelled; no age when the
 * server sent no claim time (never empty brackets, and nothing at all with neither).
 */
function sessionLine(orchestrator: OrchestratorState, now: number): string {
  const { label, claimedAt } = orchestrator;
  // toMs is 0 for a time that doesn't parse: leave the age out rather than say "20000d ago".
  const age = claimedAt && toMs(claimedAt) ? `linked ${formatRelative(claimedAt, now)}` : "";
  if (!label) return age && `Session ${age}`;
  return age ? `Session: ${label}, ${age}` : `Session: ${label}`;
}

/** The connection in words at `now` (epoch ms). */
export function connectionWords(state: AppState, now: number): ConnectionWords {
  const { connection, server } = state;
  if (connection.status === "offline") {
    const seconds = Math.max(0, Math.ceil((connection.retryAt - now) / MS_PER_SECOND));
    const parts = [OFFLINE_WORDS, `retrying in ${seconds}s`];
    return { ...words("offline", parts, [], true), spoken: OFFLINE_WORDS };
  }
  if (!server) return words("connecting", ["Connecting…"], []);
  const { orchestrator } = server;
  const link = claudeLink(orchestrator);
  if (link === "none") {
    const parts = ["No Claude session", 'run "console claim" in Claude Code'];
    return words("none", parts, [FIX_HINT], true);
  }
  if (link === "closed") {
    const detail = [sessionLine(orchestrator, now), FIX_HINT];
    return words("closed", ["Claude session closed"], detail, true);
  }
  const { turn } = orchestrator;
  const session = sessionLine(orchestrator, now);
  // The turn hook missing explains `state unknown`: a warning, with the check's words and the fix's place.
  const hook = turn.state === "unknown" ? failingTurnHook(state.health.checks) : null;
  if (hook) {
    const parts = ["Claude", HOOK_MISSING_WORDS];
    return words("hook-missing", parts, [hook.words, HOOK_MISSING_FIX, session], true);
  }
  // The hook case is handled above, so the plain turn words are the rest of
  // turnCauseWords. Stale is a warning: worded, and in the warning colour as well.
  const parts = ["Claude", turnWords(turn, now)];
  const linked = words(turn.state, parts, [session], turn.state === "stale");
  return { ...linked, spoken: `Claude · ${SPOKEN_TURN[turn.state]}` };
}
