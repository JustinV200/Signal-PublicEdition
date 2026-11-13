// A setup command's output under the control that ran it: the result in words
// (with a mark, never colour alone), the live lines in a scrolling block, and
// on a failure the Hand to Claude button with those lines.
import { useEffect, useRef } from "react";
import { HandToClaude } from "./HandToClaude";
import type { SetupRun } from "./useSetupRun";
import styles from "../setup.module.css";

// Setup CLI exit codes (tools/setup cli/agent.py); -1 is a stream cut short.
const EXIT_WORDS: Record<number, string> = {
  0: "✓ done",
  1: "✗ failed",
  2: "✗ refused (unknown tool or step)",
  3: "! needs you: see the lines above",
  127: "✗ uv isn't installed or isn't on PATH",
};
const CUT_SHORT = "✗ stopped before it finished";
// What a hand-off quotes: the end of the log, where the error is.
const HANDOFF_LINES = 40;

/** Words for a finished run's exit code. */
export function exitWords(exit: number): string {
  return EXIT_WORDS[exit] ?? (exit < 0 ? CUT_SHORT : `✗ failed (exit ${exit})`);
}

interface OutputLogProps {
  run: SetupRun;
  /** What was being done, for the hand-off, e.g. "Mail: Sign in". */
  what: string;
}

/** The log; nothing until the control has run something. */
export function OutputLog({ run, what }: OutputLogProps) {
  const { lines, exit, running, error } = run;
  const logRef = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight; // follow live output
  }, [lines.length]);
  if (!running && exit === null && !error) return null;
  const failed = error !== null || (exit !== null && exit !== 0 && exit !== 3);
  return (
    <div className={styles.output}>
      <div className={styles.outputHead} role="status">
        {running ? "… running" : error ? `✗ ${error}` : exit !== null && exitWords(exit)}
      </div>
      {lines.length > 0 && (
        <pre ref={logRef} className={styles.log}>
          {lines.join("\n")}
        </pre>
      )}
      {failed && !running && (
        <HandToClaude what={what} output={[...lines.slice(-HANDOFF_LINES), error ?? ""]} />
      )}
    </div>
  );
}
