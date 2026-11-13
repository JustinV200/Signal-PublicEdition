// The one button of the console. Every clickable control that is not a tab or
// a list row goes through here, so they all share the same bordered shape,
// hover / press / focus states, shortcut hint, pending wording and the
// disabled-with-a-reason caption.
import type { ReactNode } from "react";
import styles from "./button.module.css";

export interface ButtonProps {
  /** A plain verb label, e.g. "Send to projector". */
  children: ReactNode;
  onClick: () => void;
  /** Keyboard shortcut shown as a small hint after the label. */
  hint?: string;
  /** Why the button is off. Set, it disables the button and shows the reason as tooltip and caption. */
  disabledReason?: string;
  /** The action is running: the label reads "Working…" and clicks are ignored. */
  pending?: boolean;
  /** Accent outline for the main action of a view. */
  primary?: boolean;
  /** For a button that opens or closes something: sets aria-expanded. */
  expanded?: boolean;
}

const PENDING_LABEL = "Working…";

/** A bordered button; renders its disabled reason as a caption right after itself. */
export function Button({
  children,
  onClick,
  hint,
  disabledReason,
  pending = false,
  primary = false,
  expanded,
}: ButtonProps) {
  const classes = [styles.btn, primary && styles.primary, pending && styles.pending].filter(
    Boolean,
  );
  return (
    <>
      <button
        type="button"
        className={classes.join(" ")}
        disabled={pending || Boolean(disabledReason)}
        title={disabledReason}
        aria-expanded={expanded}
        onClick={onClick}
      >
        {pending ? PENDING_LABEL : children}
        {hint && !pending && <kbd className={styles.hint}>{hint}</kbd>}
      </button>
      {disabledReason && !pending && <span className={styles.reason}>{disabledReason}</span>}
    </>
  );
}
