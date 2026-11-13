// Permissions: what setup will add to Claude Code for the finished tools (MCP
// servers, permission rules, hooks), from `setup plan`, shown in full before
// the one confirmation. "Write this" runs `setup wire --yes`; it never sets a
// permission mode.
import { Button } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import styles from "../setup.module.css";
import { useSetupQuery } from "../useSetupQuery";

/** The plan, Write this, and Not now. */
export function PermissionsScreen({ next }: { next: () => void }) {
  const plan = useSetupQuery("plan", { command: "plan" }, (lines) => lines.join("\n"));
  const runner = useSetupRun();
  const wire = async () => {
    const result = await runner.run({ command: "wire" });
    plan.reload();
    if (result?.exit === 0) next();
  };
  return (
    <section className={styles.screen}>
      <p className={styles.note}>
        What setup will add to Claude Code for the tools that are done. Your own entries in
        .mcp.json and .claude/settings.local.json are kept.
      </p>
      <pre className={styles.log}>{plan.data ?? plan.error ?? "…"}</pre>
      <div className={styles.controls}>
        <Button primary onClick={() => void wire()} pending={runner.running}>
          Write this
        </Button>
        <Button onClick={next}>Not now</Button>
      </div>
      {runner.exit === 0 && (
        <p className={styles.note} role="status">
          ✓ Written. Restart Claude Code (or run /mcp) to load the new tools.
        </p>
      )}
      <OutputLog run={runner} what="Writing the Claude Code permissions (setup wire)" />
    </section>
  );
}
