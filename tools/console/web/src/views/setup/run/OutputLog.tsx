// A setup command's output under the control that ran it: the result in words
// (with a mark, never colour alone), the live lines in a scrolling block (the
// CLI's JSON shown as the words it holds, readableLog.ts), and on a failure
// the Hand to Claude button with the raw lines, JSON included, for Claude to
// read. A busy answer (409: another command is running) is no failure, so it
// never goes to Claude.
import { useEffect, useRef } from "react";
import { Mark } from "../../../ui";
import type { MarkShape } from "../../../ui";
import { HandToClaude } from "./HandToClaude";
import { NEEDS_YOU, needsYouWords, readableLines } from "./readableLog";
import type { SetupRun } from "./useSetupRun";
import styles from "../setup.module.css";

/** A run's result: words led by a ui `Mark` shape (none for `!`, which Plex has). */
interface ExitLook {
  mark: MarkShape | null;
  words: string;
}

// Setup CLI exit codes (tools/setup cli/agent.py); -1 is a stream cut short.
const EXIT_LOOKS: Record<number, ExitLook> = {
  0: { mark: "check", words: "done" },
  1: { mark: "cross", words: "failed" },
  2: { mark: "cross", words: "refused (unknown tool or step)" },
  3: { mark: null, words: NEEDS_YOU }, // bare: ClaimLink shows no log; OutputLog words its own
  127: { mark: "cross", words: "uv isn't installed or isn't on PATH" },
};
const CUT_SHORT: ExitLook = { mark: "cross", words: "stopped before it finished" };
// A batch (`setup auto`) that stopped: AutoStops names each stop under the log.
const STOPS_BELOW: ExitLook = { mark: null, words: "! needs you: see below" };
const EXIT_NEEDS_YOU = 3;
// What a hand-off quotes: the end of the log, where the error is.
const HANDOFF_LINES = 40;

/** Words and mark for a finished run's exit code. */
export function exitLook(exit: number): ExitLook {
  return (
    EXIT_LOOKS[exit] ?? (exit < 0 ? CUT_SHORT : { mark: "cross", words: `failed (exit ${exit})` })
  );
}

/** A finished run's result line: exit 3 quotes what it needs, or points at the stops below. */
function finishedLook(exit: number, lines: readonly string[], hasStopsBelow: boolean): ExitLook {
  if (exit !== EXIT_NEEDS_YOU) return exitLook(exit);
  return hasStopsBelow ? STOPS_BELOW : { mark: null, words: needsYouWords(lines) };
}

interface OutputLogProps {
  run: SetupRun;
  /** What was being done, for the hand-off, e.g. "Mail: Sign in". */
  what: string;
  /** A batch whose stops AutoStops lists under the log, so "needs you" points down. */
  hasStopsBelow?: boolean;
}

/** The log; nothing until the control has run something. */
export function OutputLog({ run, what, hasStopsBelow = false }: OutputLogProps) {
  const { lines, exit, running, error, busy } = run;
  const logRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight; // follow live output
  }, [lines.length]);
  if (!running && exit === null && !error) return null;
  const failed = !busy && (error !== null || (exit !== null && exit !== 0 && exit !== 3));
  const look: ExitLook | null = running
    ? { mark: null, words: "… running" }
    : error
      ? { mark: busy ? null : "cross", words: busy ? `! busy: ${error}` : error }
      : exit !== null
        ? finishedLook(exit, lines, hasStopsBelow)
        : null;
  const shown = readableLines(lines);
  return (
    <div className={styles.output}>
      <div className={styles.outputHead} role="status">
        {look?.mark && <Mark shape={look.mark} />}
        {look?.mark && " "}
        {look?.words}
      </div>
      {shown.length > 0 && (
        <pre ref={logRef} className={`panel ${styles.log}`}>
          {shown.join("\n")}
        </pre>
      )}
      {failed && !running && (
        <HandToClaude what={what} output={[...lines.slice(-HANDOFF_LINES), error ?? ""]} />
      )}
    </div>
  );
}
