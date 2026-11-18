// The result strip: one line above the input line on every view but Chat
// (whose action rows carry their own outcome and Retry), saying what the last
// button or command did: `<action> · done: <result>` for 30 s, or `<action> ·
// failed: <error>` with Retry and Dismiss until dismissed or another action
// runs. Its row is always there, empty when idle, so a result arriving never
// moves the view or the input line. Only the words are the `role="status"`
// live region, so a screen reader never reads the buttons with each change.
import { useEffect, useState } from "react";
import { focusInput } from "../input";
import { doneClearsAt, lastActionRow, useConfirmGate, useStore } from "../state";
import type { LocalMessage } from "../state";
import { Button } from "../ui";
import styles from "./app.module.css";

interface ResultStripProps {
  /** Id of the failed row the owner dismissed; it stays hidden. */
  dismissedId: string | null;
  onDismiss: (id: string) => void;
}

/** `<action> · done: <result>` or `<action> · failed: <error>`, in words. */
function resultWords(row: LocalMessage): { verdict: string; detail?: string } {
  if (row.delivery === "failed") return { verdict: "failed", detail: row.error ?? "not delivered" };
  return { verdict: "done", detail: row.result };
}

/**
 * Moves the strip's clock to `clearsAt` when that time comes: one timeout per
 * shown done result instead of a ticker while the strip is up.
 */
function useClearAt(clearsAt: number | null, setNow: (now: number) => void): void {
  useEffect(() => {
    if (clearsAt === null) return;
    // At least clearsAt, so a timer that fires a hair early still clears it.
    const timer = setTimeout(() => setNow(Math.max(Date.now(), clearsAt)), clearsAt - Date.now());
    return () => clearTimeout(timer);
  }, [clearsAt, setNow]);
}

/** The strip's fixed row, filled while the last action has a result to show. */
export function ResultStrip({ dismissedId, onDismiss }: ResultStripProps) {
  const { state } = useStore();
  const { request } = useConfirmGate();
  // Read once at mount, then moved only by useClearAt: a done that lands later is
  // newer than this, so it shows until its own timeout moves the clock past it.
  const [now, setNow] = useState(() => Date.now());
  const row = lastActionRow(state.messages, now);
  useClearAt(row ? doneClearsAt(row) : null, setNow);
  const shown = row && row.id !== dismissedId ? row : null;
  const words = shown ? resultWords(shown) : null;
  const detail = words?.detail ? `: ${words.detail}` : "";

  // Retry goes through the confirm gate like the first click, so a load over a
  // drawing put up since then still asks. The buttons leave with the result, so
  // focus goes back to the input line instead of the page body.
  function retry(): void {
    if (shown?.origin?.kind !== "action") return;
    request(shown.origin.action, shown.origin.args);
    focusInput();
  }
  function dismiss(): void {
    if (shown) onDismiss(shown.id);
    focusInput();
  }

  return (
    <div className={styles.strip}>
      <div className={`frame ${styles.stripRow}`}>
        {/* Always there (empty when idle), so the live region exists before it
            fills. One line at any width: a long error ends in an ellipsis, with
            the whole line as its tooltip (and in full in Chat's row). */}
        <span
          className={styles.stripWords}
          role="status"
          title={shown && words ? `${shown.text} · ${words.verdict}${detail}` : undefined}
        >
          {shown && words && (
            <>
              {shown.text} ·{" "}
              <span className={words.verdict === "failed" ? styles.stripFailed : undefined}>
                {words.verdict}
              </span>
              {detail}
            </>
          )}
        </span>
        {words?.verdict === "failed" && (
          <>
            <Button onClick={retry}>Retry</Button>
            <Button onClick={dismiss}>Dismiss</Button>
          </>
        )}
      </div>
    </div>
  );
}
