// The Tools page (Ctrl+8): every tool in the setup registry with its live
// health, Active, Down or Not set up, each as a mark and a word, read from
// `setup status --json` (the setup CLI runs each finished tool's check with a
// short timeout). Each row's button opens the setup wizard at that tool.
import { firstJson, parseHealth } from "../../api";
import { useStore } from "../../state";
import { Button } from "../../ui";
import { HealthList, healthCounts, useSetupQuery } from "../setup";
import styles from "./tools.module.css";

const HINT =
  "Each Signal tool and whether it works right now: Active (set up and its check passes), Down (set up, but its check fails or it isn't running) or Not set up. Checks run when this page opens and on Check again.";

/** The tools view. */
export function ToolsView() {
  const { dispatch } = useStore();
  const health = useSetupQuery("status", { command: "status" }, (l) => parseHealth(firstJson(l)));
  const rows = health.data ?? [];
  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Tools</span>
        <span className={styles.meta}>
          {health.loading
            ? "checking…"
            : health.error
              ? `Not updating: ${health.error}`
              : healthCounts(rows)}
        </span>
        <span className={styles.actions}>
          <Button onClick={health.reload} pending={health.loading}>
            Check again
          </Button>
          <Button onClick={() => dispatch({ type: "openSetup", tool: null })}>Open setup</Button>
        </span>
      </div>
      <p className={styles.hint}>{HINT}</p>
      <HealthList rows={rows} />
    </div>
  );
}
