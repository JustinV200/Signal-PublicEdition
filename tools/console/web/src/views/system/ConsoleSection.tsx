// System's CONSOLE group: the console's own checks (GET /api/health, what
// `console doctor` prints) through setup's HealthList, the same list the
// TOOLS group uses. A row that isn't ok shows its fix and the exact command
// with Copy; there is no button, since the console can't fix itself from
// here. The shell reads the checks into the store (at sign-in, on opening
// System and on Refresh); Check again reads them now.
import { useStore } from "../../state";
import { Button } from "../../ui";
import { checkCounts, consoleItem, HealthList } from "../setup";
import { Section } from "./Section";
import styles from "./system.module.css";

/** The console group. */
export function ConsoleSection() {
  const { state, dispatch } = useStore();
  const { checks, error, loading } = state.health;
  const meta = error
    ? `Not updating: ${error}`
    : checks
      ? checkCounts(checks)
      : loading
        ? "checking…"
        : "not checked yet";
  return (
    <Section
      title="Console"
      meta={<span className={styles.meta}>{meta}</span>}
      actions={
        <Button onClick={() => dispatch({ type: "recheckHealth" })} pending={loading}>
          Check again
        </Button>
      }
    >
      <HealthList items={(checks ?? []).map(consoleItem)} />
    </Section>
  );
}
