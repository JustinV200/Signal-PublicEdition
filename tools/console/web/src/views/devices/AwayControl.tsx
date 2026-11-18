// The owner's Away/Here toggle (the brief's away mode). Unlike the other
// buttons it acts directly through POST /api/away instead of asking Claude:
// it is the owner's own switch. The state is always in words (status'
// awayWords): `Here`, `Away until Thu 17:00`, `Away (ends by itself in 3 days)`
// or `Asleep (sleep mode)`. An optional "until" box (a weekday, tomorrow, or a
// date) goes with I'm away, and Enter in it does the same; empty means the
// brief's 3 days.
import { useState } from "react";
import type { KeyboardEvent } from "react";
import { setAway, UnauthorizedError } from "../../api";
import type { AwayInfo } from "../../api";
import { useStore } from "../../state";
import { AWAY_DEFAULT_DAYS, awayWords } from "../../status";
import { Button } from "../../ui";
import styles from "./devices.module.css";

interface AwayControlProps {
  away: AwayInfo | null;
  onChange: (away: AwayInfo) => void;
}

const UNREADABLE = "Can't tell right now whether you're here or away.";
const UNTIL_EXAMPLES = "sunday, tomorrow, 2026-10-25";
const UNTIL_CAPTION = `Empty = ${AWAY_DEFAULT_DAYS} days.`;
const UNTIL_ID = "away-until";
const UNTIL_CAPTION_ID = "away-until-caption";
const ASLEEP_NOTE = "Sleep mode decides this; it ends when you wake.";
// The server's cap on the until text (signal_console.away).
const MAX_UNTIL_CHARS = 40;

/** The away block: System's YOU group. */
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
  // Enter in the box is the same as I'm away.
  const onUntilKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void toggle(true);
  };

  const isHere = away?.state === "here";
  const isAsleep = away?.state === "asleep";
  return (
    <div className={`panel ${styles.away}`}>
      <span className="hud-label">You</span>
      <span className={styles.awayState}>{away ? awayWords(away) : UNREADABLE}</span>
      {away && away.note && <span className={styles.awayNote}>{away.note}</span>}
      <span className={styles.awayActions}>
        {isAsleep && <span className={styles.awayNote}>{ASLEEP_NOTE}</span>}
        {isHere && (
          <>
            <label className={styles.untilLabel} htmlFor={UNTIL_ID}>
              until
            </label>
            <input
              id={UNTIL_ID}
              className={styles.until}
              value={until}
              onChange={(event) => setUntil(event.target.value)}
              onKeyDown={onUntilKey}
              placeholder={UNTIL_EXAMPLES}
              aria-describedby={UNTIL_CAPTION_ID}
              maxLength={MAX_UNTIL_CHARS}
            />
            <Button onClick={() => void toggle(true)}>{busy ? "Saving…" : "I'm away"}</Button>
            <span id={UNTIL_CAPTION_ID} className={styles.awayNote}>
              {UNTIL_CAPTION}
            </span>
          </>
        )}
        {!isHere && !isAsleep && (
          <Button
            onClick={() => void toggle(false)}
            disabledReason={away ? undefined : "can't tell whether you're away"}
          >
            {busy ? "Saving…" : "I'm back"}
          </Button>
        )}
      </span>
      {problem && <p className={styles.problem}>{problem}</p>}
    </div>
  );
}
