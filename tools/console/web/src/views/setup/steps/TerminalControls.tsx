// A step that needs the owner's own terminal (a password, Windows Hello, a
// typed client ID): the wizard never takes those. "Open a terminal" starts a
// PowerShell window on `setup.ps1 step <tool> <step>`, which runs just that
// step, so the secret is typed there and never passes through this page.
// "Check again" re-reads the step's saved status (as does coming back to the
// window): a closed terminal leaves the step as it was. It reads "Working…"
// while it reads, then says what it found and when, so a click that changes
// nothing still shows it happened. Both buttons follow the wizard's one running
// state (run/runningState.tsx).
import { useState } from "react";
import { firstJson, openSetupTerminal, parseTools, UnauthorizedError } from "../../../api";
import type { StepStatus } from "../../../api";
import { useStore } from "../../../state";
import { Button } from "../../../ui";
import { buttonLook, useRunningState, useSetupRun } from "../run";
import styles from "../setup.module.css";

// Open a terminal's key in the running state. It starts no setup command here
// (the terminal runs the step), so it never holds the state; it only yields:
// off with "another step is running" while any of the wizard's commands runs.
const OPEN_KEY = "terminal:open";

// What Check again found, by the step's saved status.
const CHECK_WORDS: Record<StepStatus, string> = {
  done: "done",
  skipped: "skipped",
  failed: "failed (see the terminal)",
  "": "not done yet",
};

interface TerminalControlsProps {
  toolId: string;
  stepId: string;
  /** Re-reads the steps' saved status. */
  onCheck: () => void;
}

/** Open a terminal, the command to type instead, and Check again. */
export function TerminalControls({ toolId, stepId, onCheck }: TerminalControlsProps) {
  const { dispatch } = useStore();
  const checker = useSetupRun();
  const { active } = useRunningState();
  const [note, setNote] = useState<string | null>(null);
  const open = async () => {
    try {
      await openSetupTerminal(toolId, stepId);
      setNote("Opened. Answer it there; this step's status updates when you come back here.");
    } catch (failure) {
      if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
      setNote(failure instanceof Error ? failure.message : String(failure));
    }
  };
  const check = async () => {
    const listed = await checker.run({ command: "list" });
    onCheck();
    if (!listed) return; // the runner's error shows below
    if (listed.exit !== 0) {
      setNote(`Couldn't check: ${listed.lines.at(-1) ?? `exit ${listed.exit}`}`);
      return;
    }
    const tool = parseTools(firstJson(listed.lines)).find((t) => t.id === toolId);
    const status = tool?.steps.find((s) => s.id === stepId)?.status ?? "";
    setNote(`Checked at ${new Date().toLocaleTimeString()}: ${CHECK_WORDS[status]}.`);
  };
  return (
    <div className={styles.form}>
      <p className={styles.note}>
        This step runs in your own terminal:{" "}
        <code>
          .\setup.cmd step {toolId} {stepId}
        </code>
      </p>
      <div className={styles.controls}>
        <Button primary onClick={() => void open()} {...buttonLook(active, OPEN_KEY)}>
          Open a terminal
        </Button>
        <Button onClick={() => void check()} {...checker.button()}>
          Check again
        </Button>
      </div>
      {(checker.error ?? note) && (
        <p className={styles.note} role="status">
          {checker.error ?? note}
        </p>
      )}
    </div>
  );
}
