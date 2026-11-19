// System's TOOLS group (formerly a tab of its own): every tool in the setup registry
// with its live health, Active, Set up but not added to Claude Code yet, Down
// or Not set up, each as a mark and a word, then what its check found and any
// fix with its command, read from `setup status --json` (the setup CLI runs
// each finished tool's check with a short timeout and reads whether its
// servers and hooks are in Claude Code's config; a tool it has no record of
// but finds working and in that config reads Active too, its words ending
// `found already set up`). A not-added row's button
// runs `setup wire` here, then the restart line shows under the header; every
// other row's button opens the setup wizard at that tool (a Fix with the
// check, which leads the tool page), and `Open setup` opens it where setup stopped.
import { firstJson, parseHealth } from "../../api";
import { useStore } from "../../state";
import { Button } from "../../ui";
import { AddResult, healthCounts, ToolHealthList, useAddToClaude, useSetupQuery } from "../setup";
import { Section } from "./Section";
import styles from "./system.module.css";

/** The tools group. */
export function ToolsSection() {
  const { dispatch } = useStore();
  const health = useSetupQuery("status", { command: "status" }, (l) => parseHealth(firstJson(l)));
  const wiring = useAddToClaude();
  const rows = health.data ?? [];
  const meta = health.loading
    ? "checking…"
    : health.error
      ? `Not updating: ${health.error}`
      : healthCounts(rows);
  return (
    <Section
      title="Tools"
      meta={<span className={styles.meta}>{meta}</span>}
      actions={
        <>
          <Button onClick={health.reload} pending={health.loading}>
            Check again
          </Button>
          <Button onClick={() => dispatch({ type: "openSetup", tool: null })}>Open setup</Button>
        </>
      }
    >
      <AddResult wiring={wiring} />
      <ToolHealthList
        rows={rows}
        onAdd={() => void wiring.add().then(health.reload)}
        addButton={wiring.runner.button()}
      />
    </Section>
  );
}
