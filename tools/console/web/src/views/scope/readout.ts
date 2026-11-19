// The text readout beside the scope: one row per fact, what needs the owner
// first, each row naming the view it opens. Pure functions of the store state,
// so ScopeView stays dumb. Every value is words; nothing leans on colour.
import { chatNewCount, pendingRows } from "../../state";
import type { AppState, View } from "../../state";
import { awayWords, newWords, startedByWords, toDotPhase } from "../../status";
import { formatClock } from "../../time";
import { actionView, boardWords, claudeWords } from "./blips";
import { splitNeedsYou } from "./needsYou";

export interface ReadoutRow {
  /** Unique per row (a label can repeat: a NEEDS YOU row per shown task). */
  key: string;
  label: string;
  value: string;
  /** The view a click or Enter opens. */
  view: View;
}

/** Ends every value while the server isn't answering: the state shown is the last one read. */
export const LAST_KNOWN = " (last known)";

// A row per shown task waiting on the owner, with what they must do, then one
// `+16 more` row for the rest (together the radar's `19 NEED YOU`); `nothing` when none.
function needsYouRows(state: AppState): ReadoutRow[] {
  const { shown, folded } = splitNeedsYou(state.tasks);
  const row = (key: string, value: string): ReadoutRow => ({
    key,
    label: "NEEDS YOU",
    value,
    view: "tasks",
  });
  if (shown.length === 0) return [row("needs-you", "nothing")];
  return [
    // `you` is set on needs_you tasks; the name stands in if a writer left it empty.
    ...shown.map((task) => row(`needs-you-${task.id}`, task.you || task.name)),
    ...(folded > 0 ? [row("more-needs-you", `+${folded} more`)] : []),
  ];
}

/** `2 new · last 14:05`; `nothing new` with no rows yet. */
function chatWords(state: AppState): string {
  const fresh = newWords(chatNewCount(state)) ?? "nothing new";
  const last = state.messages.at(-1);
  return last ? `${fresh} · last ${formatClock(last.at)}` : fresh;
}

function voiceWords(state: AppState): string {
  const voice = state.server?.voice;
  if (!voice?.running) return "stopped";
  const startedBy = startedByWords(voice.startedBy);
  const by = startedBy ? ` · ${startedBy}` : "";
  return `running · ${toDotPhase(voice)}${by}`;
}

/** `here`, `away until Thu 17:00`, `asleep (sleep mode)`: System's words, lower-cased like the other values. */
function youWords(state: AppState): string {
  const away = state.server?.away;
  if (!away) return "unknown";
  const words = awayWords(away);
  return words.charAt(0).toLowerCase() + words.slice(1);
}

/** A RUNNING row per button request still in flight (the same set the buttons pend on). */
function runningRows(state: AppState, now: number): ReadoutRow[] {
  return pendingRows(state.messages, now).map((row) => ({
    key: `running-${row.id}`,
    label: "RUNNING",
    value: row.text,
    view: actionView(row),
  }));
}

/**
 * The readout rows at `now` (epoch ms): NEEDS YOU (at most NEEDS_YOU_SHOWN + 1 rows), CHAT,
 * CLAUDE, VOICE, BOARD, YOU, then RUNNING while a button runs. Offline with a state read
 * before, each value ends with LAST_KNOWN.
 */
export function buildReadout(state: AppState, now: number): ReadoutRow[] {
  const { server } = state;
  // No empty brackets for an unlabelled session.
  const label = server?.orchestrator.claimed ? server.orchestrator.label : "";
  const session = label ? ` (${label})` : "";
  const rows: ReadoutRow[] = [
    ...needsYouRows(state),
    { key: "chat", label: "CHAT", value: chatWords(state), view: "chat" },
    { key: "claude", label: "CLAUDE", value: `${claudeWords(state, now)}${session}`, view: "chat" },
    { key: "voice", label: "VOICE", value: voiceWords(state), view: "voice" },
    {
      key: "board",
      label: "BOARD",
      value: boardWords(state),
      view: "boards",
    },
    { key: "you", label: "YOU", value: youWords(state), view: "system" },
    ...runningRows(state, now),
  ];
  const isStale = state.connection.status === "offline" && server !== null;
  return isStale ? rows.map((row) => ({ ...row, value: `${row.value}${LAST_KNOWN}` })) : rows;
}
