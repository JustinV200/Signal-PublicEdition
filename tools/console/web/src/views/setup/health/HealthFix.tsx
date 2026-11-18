// What to do about a check, under its health row and atop a tool page that a
// Fix opened: the fix in words, then the exact command with Copy. The page
// never runs the command; the owner pastes it into a terminal.
import { CopyButton } from "../../../ui";
import styles from "./health.module.css";

const COPIED_NOTE = "Copied. Paste it into a terminal at the repo's root folder.";

interface HealthFixProps {
  /** One sentence on what to do; "" when the check gave only a command. */
  fix: string;
  /** A command that runs as shown; "" for none. */
  command: string;
  className?: string;
}

/** `Fix: <words>`, then the command in code and Copy. */
export function HealthFix({ fix, command, className }: HealthFixProps) {
  return (
    <div className={`${styles.fixBlock} ${className ?? ""}`}>
      <span>
        <strong>Fix:</strong> {fix || "run this:"}
      </span>
      {command && (
        <span className={styles.command}>
          <code className={styles.commandText}>{command}</code>
          <CopyButton text={command} copiedNote={COPIED_NOTE} />
        </span>
      )}
    </div>
  );
}
