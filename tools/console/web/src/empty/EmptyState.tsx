// The one empty state of Chat, Voice, Boards and Tasks: a dashed ring (nothing
// here yet), a HUD label naming what is missing, and what to expect in `--fg-2`.
// The label carries the meaning; the ring is a second, decorative cue.
import type { ReactNode } from "react";
import { Mark } from "../ui";
import styles from "./empty.module.css";

interface EmptyStateProps {
  /** What is missing, in sentence case (the HUD label sets it in capitals). */
  label: string;
  /** The line under it: what will show here, or how to start (Chat adds its claim help). */
  children: ReactNode;
}

/** A view's or list's empty state. */
export function EmptyState({ label, children }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <span className={styles.mark}>
        <Mark shape="dashedRing" />
      </span>
      <span className="hud-label">{label}</span>
      <div className={styles.line}>{children}</div>
    </div>
  );
}
