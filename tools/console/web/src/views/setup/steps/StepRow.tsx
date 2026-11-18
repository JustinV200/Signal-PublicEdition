// One setup step of a tool: its status as a mark and a word (never colour
// alone), its title and kind, then the controls that run it. Every control
// runs a fixed setup CLI command; nothing here decides how a step works.
import type { SetupStep, StepStatus } from "../../../api";
import { Mark } from "../../../ui";
import type { MarkShape } from "../../../ui";
import styles from "../setup.module.css";
import { StepControls } from "./StepControls";

/** A step status's word and its ui `Mark` shape; skipped's dash is plain text (Plex has it). */
interface StatusLook {
  mark: MarkShape | null;
  words: string;
}

const STATUS_LOOKS: Record<StepStatus, StatusLook> = {
  done: { mark: "check", words: "done" },
  skipped: { mark: null, words: "– skipped" },
  failed: { mark: "cross", words: "failed" },
  "": { mark: "ring", words: "to do" },
};

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
  const look = STATUS_LOOKS[step.status];
  return (
    <li className={styles.step}>
      <div className={styles.stepHead}>
        <span className={`${styles.status} ${styles[`status_${step.status || "todo"}`] ?? ""}`}>
          {look.mark && <Mark shape={look.mark} />}
          {look.mark && " "}
          {look.words}
        </span>
        <span className={styles.stepTitle}>{step.title}</span>
        <span className={styles.note}>{tags.filter(Boolean).join(" · ")}</span>
      </div>
      <StepControls toolId={toolId} step={step} onChanged={onChanged} />
    </li>
  );
}
