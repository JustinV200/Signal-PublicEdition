// One setup step of a tool: its status as a mark and a word (never colour
// alone), its title and kind, then the controls that run it. Every control
// runs a fixed setup CLI command; nothing here decides how a step works.
import type { SetupStep, StepStatus } from "../../../api";
import styles from "../setup.module.css";
import { StepControls } from "./StepControls";

const STATUS_WORDS: Record<StepStatus, string> = {
  done: "✓ done",
  skipped: "– skipped",
  failed: "✗ failed",
  "": "○ to do",
};

/** A step's status in words with its mark. */
export function stepStatusWords(status: StepStatus): string {
  return STATUS_WORDS[status];
}

interface StepRowProps {
  toolId: string;
  step: SetupStep;
  /** Re-read the tools after something changed a step's status. */
  onChanged: () => void;
}

/** The row: status, title, optional/terminal tags, then the controls. */
export function StepRow({ toolId, step, onChanged }: StepRowProps) {
  const tags = [
    step.optional ? "optional" : "required",
    step.terminal ? "needs your terminal" : "",
  ];
  return (
    <li className={styles.step}>
      <div className={styles.stepHead}>
        <span className={`${styles.status} ${styles[`status_${step.status || "todo"}`] ?? ""}`}>
          {stepStatusWords(step.status)}
        </span>
        <span className={styles.stepTitle}>{step.title}</span>
        <span className={styles.note}>{tags.filter(Boolean).join(" · ")}</span>
      </div>
      <StepControls toolId={toolId} step={step} onChanged={onChanged} />
    </li>
  );
}
