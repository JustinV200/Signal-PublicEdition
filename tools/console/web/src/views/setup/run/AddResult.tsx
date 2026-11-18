// What `Add to Claude Code` did, wherever it can be clicked: while running or
// after a failure, the run's log (with Hand to Claude); after it worked, the
// restart line. The tools are then in Claude Code's config, but Claude Code
// only loads them when it starts, so the line stays until the owner leaves
// the page, and Summary repeats it at its top.
import { Mark } from "../../../ui";
import styles from "../setup.module.css";
import { OutputLog } from "./OutputLog";
import { ADD_WHAT } from "./useAddToClaude";
import type { AddToClaude } from "./useAddToClaude";

const RESTART_LINE =
  "Added to Claude Code. Now start (or restart) Claude Code in this folder so it loads the new tools.";

/** The restart line once added, else the wire run's log (nothing before any run). */
export function AddResult({ wiring }: { wiring: AddToClaude }) {
  if (!wiring.added) return <OutputLog run={wiring.runner} what={ADD_WHAT} />;
  return (
    <p className={styles.restart} role="status">
      <Mark shape="check" /> {RESTART_LINE}
    </p>
  );
}
