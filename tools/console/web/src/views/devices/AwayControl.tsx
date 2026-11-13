// the owner's Away/Here toggle (the brief's away mode). Unlike the other
// buttons it acts directly through POST /api/away instead of asking Claude:
// it is the owner's own switch. The state is always in words: `Here`, `Away until
// Thu 17:00`, or `Asleep (sleep mode)`. An optional "until" (a weekday,
// tomorrow, or a date) goes with I'm away; empty means the brief's 3 days.
import { useState } from "react";
import { setAway, UnauthorizedError } from "../../api";
import type { AwayInfo } from "../../api";
import { useStore } from "../../state";
import { formatClock, toMs } from "../../time";
import { Button } from "../../ui";
import styles from "./devices.module.css";

interface AwayControlProps {
  away: AwayInfo | null;
  onChange: (away: AwayInfo) => void;
}

const UNREADABLE = "Away mode can't be read right now.";
const UNTIL_HINT = "until (optional): sunday, tomorrow, 2026-10-25";
const ASLEEP_NOTE = "Sleep mode decides this; it ends when you wake.";
// The server's cap on the until text (signal_console.away).
const MAX_UNTIL_CHARS = 40;

/** `Away until Thu 17:00`, `Here` or `Asleep (sleep mode)`. */
export function awayWords(away: AwayInfo): string {
  if (away.state === "here") return "Here";
  if (away.state === "asleep") return "Asleep (sleep mode)";
  if (!away.endsAt) return "Away";
  const day = new Date(toMs(away.endsAt)).toLocaleDateString(undefined, { weekday: "short" });
  return `Away until ${day} ${formatClock(away.endsAt)}`;
}

/** The away block of the Devices view. */
export function AwayControl({ away, onChange }: AwayControlProps) {
  const { dispatch } = useStore();
  const [until, setUntil] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const toggle = async (on: boolean) => {
    if (busy) return;
    setBusy(true);
    setProblem(null);
    try {
      onChange(await setAway(on, on ? until.trim() : ""));
      setUntil("");
    } catch (failure) {
      if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
      setProblem(failure instanceof Error ? failure.message : String(failure));
    } finally {
      setBusy(false);
    }
  };

  const isHere = away?.state === "here";
  const isAsleep = away?.state === "asleep";
  return (
    <div className={styles.away}>
      <span className="hud-label">You</span>
      <span className={styles.awayState}>{away ? awayWords(away) : UNREADABLE}</span>
      {away && away.note && <span className={styles.awayNote}>{away.note}</span>}
      <span className={styles.awayActions}>
        {isAsleep && <span className={styles.awayNote}>{ASLEEP_NOTE}</span>}
        {isHere && (
          <>
            <input
              className={styles.until}
              value={until}
              onChange={(event) => setUntil(event.target.value)}
              placeholder={UNTIL_HINT}
              aria-label="away until"
              maxLength={MAX_UNTIL_CHARS}
            />
            <Button onClick={() => void toggle(true)}>{busy ? "Saving…" : "I'm away"}</Button>
          </>
        )}
        {!isHere && !isAsleep && (
          <Button
            onClick={() => void toggle(false)}
            disabledReason={away ? undefined : "away mode can't be read"}
          >
            {busy ? "Saving…" : "I'm back"}
          </Button>
        )}
      </span>
      {problem && <p className={styles.problem}>{problem}</p>}
    </div>
  );
}
