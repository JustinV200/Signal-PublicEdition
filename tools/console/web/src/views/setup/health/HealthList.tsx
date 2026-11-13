// A list of tools with their live health: mark, name, state label, what the
// check said, the platform, and the button that opens the setup wizard at
// that tool's steps. Used by the Tools page and the wizard's summary.
import type { ToolHealth } from "../../../api";
import { useStore } from "../../../state";
import { Button } from "../../../ui";
import styles from "../setup.module.css";
import { healthAction, healthLook } from "./healthWords";

const NOT_HERE = "can't run on this OS";

/** One row per tool. */
export function HealthList({ rows }: { rows: readonly ToolHealth[] }) {
  const { dispatch } = useStore();
  return (
    <ul className={styles.list}>
      {rows.map((row) => {
        const look = healthLook(row.state);
        return (
          <li key={row.id} className={styles.healthRow}>
            <span
              className={`${styles.mark} ${styles[`health_${row.state}`] ?? ""}`}
              aria-hidden="true"
            >
              {look.mark}
            </span>
            <span className={styles.stepTitle}>{row.name}</span>
            <span className={styles.healthWords}>
              <strong>{look.label}</strong> {row.detail && `· ${row.detail}`}{" "}
              <span className={styles.note}>[{row.platform}]</span>
            </span>
            <span className={styles.controls}>
              <Button
                onClick={() => dispatch({ type: "openSetup", tool: row.id })}
                disabledReason={row.supportedHere ? undefined : NOT_HERE}
              >
                {healthAction(row)}
              </Button>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
