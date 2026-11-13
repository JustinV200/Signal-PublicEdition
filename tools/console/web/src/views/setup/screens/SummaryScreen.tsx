// The end of setup: each picked tool's live health (`setup status --json`
// runs every finished tool's check), with Fix buttons, Check again, and the
// way on to the tour.
import { firstJson, parseHealth } from "../../../api";
import type { SetupTool } from "../../../api";
import { Button } from "../../../ui";
import { HealthList, healthCounts } from "../health";
import { isChosen } from "../wizardScreens";
import styles from "../setup.module.css";
import { useSetupQuery } from "../useSetupQuery";

interface SummaryScreenProps {
  tools: SetupTool[];
  next: () => void;
}

/** Health of the picks, Check again and Take the tour. */
export function SummaryScreen({ tools, next }: SummaryScreenProps) {
  const health = useSetupQuery("status", { command: "status" }, (l) => parseHealth(firstJson(l)));
  const picked = new Set(tools.filter(isChosen).map((tool) => tool.id));
  const rows = (health.data ?? []).filter((row) => picked.has(row.id));
  return (
    <section className={styles.screen}>
      <p className={styles.note}>
        {health.loading
          ? "… checking each tool"
          : health.error
            ? `✗ ${health.error}`
            : healthCounts(rows)}
      </p>
      <HealthList rows={rows} />
      <div className={styles.controls}>
        <Button onClick={health.reload} pending={health.loading}>
          Check again
        </Button>
        <Button primary onClick={next}>
          Take the tour
        </Button>
      </div>
      <p className={styles.note}>The Tools tab shows this any time.</p>
    </section>
  );
}
