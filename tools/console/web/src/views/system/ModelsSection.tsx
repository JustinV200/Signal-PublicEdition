// System's MODELS group: the model strip, and, while the session hook isn't
// installed, a line in its header that says why the model can read `unknown`
// and a button that scrolls to the CONSOLE group's Session hook row (and
// focuses it), where the fix and its command are.
import { SESSION_HOOK_CHECK } from "../../api";
import { ModelStrip } from "../../models";
import { useStore } from "../../state";
import { Button, Mark } from "../../ui";
import { consoleRowKey, healthRowId } from "../setup";
import { Section } from "./Section";
import styles from "./system.module.css";

/** Scrolls the CONSOLE group's row for `checkId` into view and focuses it. */
function showConsoleRow(checkId: string): void {
  const row = document.getElementById(healthRowId(consoleRowKey(checkId)));
  row?.scrollIntoView({ block: "center" });
  row?.focus({ preventScroll: true });
}

/** The models group. */
export function ModelsSection() {
  const { state } = useStore();
  const hook = state.health.checks?.find((check) => check.id === SESSION_HOOK_CHECK);
  const isHookMissing = hook !== undefined && hook.level !== "ok";
  const meta = isHookMissing && (
    <span className={styles.meta}>
      <Mark shape={hook.level === "fail" ? "cross" : "half"} /> the session hook isn't installed, so
      the console can't see which model runs
    </span>
  );
  const actions = isHookMissing && (
    <Button onClick={() => showConsoleRow(SESSION_HOOK_CHECK)}>Show the Console row</Button>
  );
  return (
    <Section title="Models" meta={meta} actions={actions}>
      <ModelStrip />
    </Section>
  );
}
