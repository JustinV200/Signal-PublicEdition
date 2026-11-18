// One group of the System view: the shared view-header line (a HUD title,
// its words, its buttons on the right), then the group's body.
import type { ReactNode } from "react";
import styles from "./system.module.css";

interface SectionProps {
  /** The group's title, e.g. "Devices" (the HUD label sets it in capitals). */
  title: string;
  /** Words beside the title, e.g. how fresh the rows are. */
  meta?: ReactNode;
  /** Buttons at the header's right end. */
  actions?: ReactNode;
  children?: ReactNode;
}

/** A titled group; screen readers get it as a region named by its title. */
export function Section({ title, meta, actions, children }: SectionProps) {
  return (
    <section className={styles.section} aria-label={title}>
      <div className="view-header">
        <h2 className="hud-label">{title}</h2>
        {meta}
        {actions && <span className={styles.actions}>{actions}</span>}
      </div>
      {children}
    </section>
  );
}
