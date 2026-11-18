// The `console open` command line with Copy, shared by the signed-out page,
// the server-down notice and Help. The server sends the full line with its
// own absolute project path (it runs from any folder); before the page has
// heard it once, the repo-relative form shows, with where to run it.
import { CopyButton } from "./CopyButton";
import styles from "./openCommand.module.css";

/** Runs only from the repo root; shown until the server's own line is known. */
const FALLBACK_COMMAND = "uv run --project tools/console --frozen --no-sync console open";
const COPIED_NOTE = "Copied. Paste it into a terminal.";

/** `lead`, then the command in inline code, then Copy. `command` null: the fallback. */
export function OpenCommand({ lead, command }: { lead: string; command: string | null }) {
  const text = command ?? FALLBACK_COMMAND;
  return (
    <div className={styles.command}>
      <div>
        {lead}
        {command === null && " (from the repo's root folder)"}:
      </div>
      <code className={styles.commandText}>{text}</code>
      <CopyButton text={text} copiedNote={COPIED_NOTE} />
    </div>
  );
}
