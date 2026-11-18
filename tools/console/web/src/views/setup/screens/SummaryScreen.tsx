// The end of setup: the restart line again when the tools were just added to
// Claude Code, then each picked tool's live health (`setup status --json`
// runs every finished tool's check), with Fix and Add to Claude Code buttons,
// Check again, then the primary Open Chat (setup is done: talk to Claude) and
// the way on to the optional Tour page. Check again joins the wizard's
// running state: it reads Working… only while nothing else runs, and is off
// with the same reason while another step does.
import { firstJson, parseHealth } from "../../../api";
import type { SetupTool } from "../../../api";
import { useStore } from "../../../state";
import { Button, Mark } from "../../../ui";
import { healthCounts, ToolHealthList } from "../health";
import { AddResult, buttonLook, useRunningState } from "../run";
import type { AddToClaude } from "../run";
import { isChosen } from "../wizardScreens";
import styles from "../setup.module.css";
import { useSetupQuery } from "../useSetupQuery";

// Check again's key in the running state; no runner holds it, so while one runs it's off.
const CHECK_KEY = "summary:check";

interface SummaryScreenProps {
  tools: SetupTool[];
  /** The wizard's wire runner: its restart line leads the page once a wire worked. */
  wiring: AddToClaude;
  next: () => void;
}

/** Health of the picks, Open Chat, Take the tour and Check again. */
export function SummaryScreen({ tools, wiring, next }: SummaryScreenProps) {
  const { dispatch } = useStore();
  const health = useSetupQuery("status", { command: "status" }, (l) => parseHealth(firstJson(l)));
  const { active } = useRunningState();
  // Not a runner (a read-only query), so it never holds the running state; it only yields to it.
  const checkLook = active ? buttonLook(active, CHECK_KEY) : { pending: health.loading };
  const picked = new Set(tools.filter(isChosen).map((tool) => tool.id));
  const rows = (health.data ?? []).filter((row) => picked.has(row.id));
  const add = () => void wiring.add().then(health.reload);
  return (
    <section className={styles.screen}>
      <AddResult wiring={wiring} />
      <p className={styles.note}>
        {health.loading ? (
          "… checking each tool"
        ) : health.error ? (
          <>
            <Mark shape="cross" /> {health.error}
          </>
        ) : (
          healthCounts(rows)
        )}
      </p>
      <ToolHealthList rows={rows} onAdd={add} addButton={wiring.runner.button()} />
      <div className={styles.controls}>
        <Button primary onClick={() => dispatch({ type: "view", view: "chat" })}>
          Open Chat
        </Button>
        <Button onClick={next}>Take the tour</Button>
        <Button onClick={health.reload} {...checkLook}>
          Check again
        </Button>
      </div>
      <p className={styles.note}>System shows this any time.</p>
    </section>
  );
}
