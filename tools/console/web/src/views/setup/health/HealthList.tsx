// A health list: one row per check, each a mark, a name and words (the state's
// label, then what the check found), and the row's button on the right. A row
// with a fix shows it underneath in words, with the exact command and Copy
// (HealthFix). System's CONSOLE and TOOLS groups and the wizard's summary all
// render through it; the caller adds the buttons, if any (ToolHealthList adds
// a tool's). Each row has an element id (healthRowId) and takes focus, so
// another group can scroll to it and land there.
import type { ReactNode } from "react";
import { Mark } from "../../../ui";
import styles from "./health.module.css";
import { HealthFix } from "./HealthFix";
import type { HealthItem } from "./healthWords";
import { healthRowId } from "./healthWords";

interface HealthListProps {
  items: readonly HealthItem[];
  /** The row's controls (a tool's Set up, Fix or Add to Claude Code); none when left out. */
  renderAction?: (item: HealthItem) => ReactNode;
}

/** One row per item. */
export function HealthList({ items, renderAction }: HealthListProps) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <li key={item.key} id={healthRowId(item.key)} tabIndex={-1} className={styles.row}>
          <span className={`${styles.mark} ${styles[`tone_${item.tone}`]}`} aria-hidden="true">
            <Mark shape={item.look.mark} />
          </span>
          <span className={styles.name}>{item.name}</span>
          <span className={styles.words}>
            <strong>{item.look.label}</strong>
            {item.words && ` · ${item.words}`}
            {item.note && <span className={styles.note}> [{item.note}]</span>}
          </span>
          <span className={styles.controls}>{renderAction?.(item)}</span>
          {(item.fix || item.command) && (
            <HealthFix fix={item.fix} command={item.command} className={styles.fix} />
          )}
        </li>
      ))}
    </ul>
  );
}
