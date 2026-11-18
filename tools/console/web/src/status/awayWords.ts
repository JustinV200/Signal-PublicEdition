// The owner's away state in words (the brief's away mode, or sleep mode),
// shared by System's YOU panel, the status line's title row and the scope's
// YOU row so they say it the same way. Words carry the state; nothing here leans on colour.
import type { AwayInfo } from "../api";
import { formatClock, toMs } from "../time";

// The brief's default length for away mode set with no end (signal_brief's AWAY_WITHOUT_END).
export const AWAY_DEFAULT_DAYS = 3;

/** The title row's away state, split so narrow widths can drop the end and keep the word. */
export interface TitleAway {
  /** `Away` or `Asleep`: always shown. */
  word: string;
  /** ` until Thu 17:00`, with its leading space; "" with no end given. */
  until: string;
  /** The tooltip: the full state and where it is changed. */
  tooltip: string;
}

/** ` until Thu 17:00`, or "" when the owner gave no end. */
function untilWords(away: AwayInfo): string {
  if (!away.endsAt) return "";
  const day = new Date(toMs(away.endsAt)).toLocaleDateString(undefined, { weekday: "short" });
  return ` until ${day} ${formatClock(away.endsAt)}`;
}

/**
 * The full state, for System's YOU panel.
 *
 * @returns `Here`, `Away until Thu 17:00`, `Away (ends by itself in 3 days)` or `Asleep (sleep mode)`.
 */
export function awayWords(away: AwayInfo): string {
  if (away.state === "here") return "Here";
  if (away.state === "asleep") return "Asleep (sleep mode)";
  return `Away${untilWords(away) || ` (ends by itself in ${AWAY_DEFAULT_DAYS} days)`}`;
}

/**
 * The title row's state, shown only when the owner isn't here.
 *
 * @returns `Away` (plus ` until Thu 17:00` when an end was given) or `Asleep`, each with
 *   its tooltip; null while here or unknown.
 */
export function titleAwayWords(away: AwayInfo | null | undefined): TitleAway | null {
  if (!away || away.state === "here") return null;
  if (away.state === "asleep")
    return {
      word: "Asleep",
      until: "",
      tooltip: "Asleep: sleep mode decides this, and it ends when you wake.",
    };
  const until = untilWords(away);
  return { word: "Away", until, tooltip: `Away${until}. System's YOU has I'm back.` };
}
