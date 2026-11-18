// The one button of the console. Every clickable control that is not a tab or
// a list row goes through here, so they all share the same bordered shape,
// text size, hover / press / focus states, shortcut hint, pending wording and
// the disabled-with-a-reason caption (or, quietly, a tooltip only).
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
  /**
   * Why the button is off, as a tooltip only (no caption), for a reason said
   * elsewhere on screen or one that would shift the layout as it comes and goes.
   */
  quietReason?: string;
  /**
   * Off only until the user does something here (Send with an empty draft):
   * the border stays solid, so the button reads as waiting, not broken.
   */
  awaitsInput?: boolean;
  /** The action is running: the label reads "Working…" and clicks are ignored. */
  pending?: boolean;
  /** The main action of a view: an accent outline, a resting fill and a 600 label. */
  primary?: boolean;
  /** For a button that opens or closes something: sets aria-expanded. */
  expanded?: boolean;
}

const PENDING_LABEL = "Working…";

/** A bordered button; renders a `disabledReason` as a caption right after itself. */
export function Button({
  children,
  onClick,
  hint,
  disabledReason,
  quietReason,
  awaitsInput = false,
  pending = false,
  primary = false,
  expanded,
}: ButtonProps) {
  const reason = disabledReason ?? quietReason;
  const classes = [
    styles.btn,
    primary && styles.primary,
    pending && styles.pending,
    awaitsInput && styles.awaits,
  ].filter(Boolean);
  return (
    <>
      <button
        type="button"
        className={classes.join(" ")}
        disabled={pending || Boolean(reason)}
        title={reason}
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
