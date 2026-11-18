// The top of a tool page that a Fix opened: why it was opened, in the check's
// own words, then its fix and command. A down tool's steps all read done, so
// without this the page would give no reason at all.
import type { ToolHealth } from "../../../api";
import { Mark } from "../../../ui";
import styles from "./health.module.css";
import { HealthFix } from "./HealthFix";
import { healthLook } from "./healthWords";

const NO_WORDS = "its check gave no reason";

/** The failing check's mark, label and words, then what to do. */
export function CheckBanner({ row }: { row: ToolHealth }) {
  const look = healthLook(row);
  return (
    <div className={`panel ${styles.banner}`} role="status">
      <div>
        <Mark shape={look.mark} /> <strong>{look.label}</strong> · {row.words || NO_WORDS}{" "}
        <span className={styles.note}>(System's last check)</span>
      </div>
      {(row.fix || row.command) && <HealthFix fix={row.fix} command={row.command} />}
    </div>
  );
}
