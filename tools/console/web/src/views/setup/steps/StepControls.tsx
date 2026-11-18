// The controls for one step, chosen by its kind (tools/setup registry):
// run/copy -> Run; confirm -> Yes / No (e.g. the browser auto-approve toggle);
// manual -> the instructions and Mark done (the console's claim step instead
// shows the live link, ClaimLink, and ticks itself); email/env -> a field and Save;
// settings -> the schema form; samples -> the samples panel. A step that needs
// the owner's own terminal gets Open a terminal instead. Optional steps can be
// skipped. A step whose registry entry names a guide shows it inline,
// collapsed (StepGuide). Each command's live output and any failure show below.
// A terminal step has no Mark done: Check again re-reads what setup saved.
// Each button runs under its own key in the wizard's one running state, so
// only the clicked one reads "Working…" and the rest are off meanwhile.
import type { ReactNode } from "react";
import type { SetupRequest, SetupStep } from "../../../api";
import { Markdown } from "../../../markdown";
import { Button, Mark } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import { SamplesPanel } from "../samples";
import { SettingsForm } from "../settings";
import styles from "../setup.module.css";
import { useSetupDraft } from "../useSetupDraft";
import { CONSOLE_ID } from "../wizardScreens";
import { CLAIM_STEP_ID, ClaimLink } from "./ClaimLink";
import { StepGuide } from "./StepGuide";
import { TerminalControls } from "./TerminalControls";

// Extra words for a confirm step, keyed `<tool>.<step>`.
const CONFIRM_NOTES: Record<string, string> = {
  "browser.auto-approve":
    "Claude may use the browser without asking before every click. The browser's own purchase, send and delete confirmations stay on either way.",
};

interface StepControlsProps {
  toolId: string;
  step: SetupStep;
  onChanged: () => void;
}

/** The kind-specific controls, a Skip for optional steps, and the output log. */
export function StepControls({ toolId, step, onChanged }: StepControlsProps) {
  const runner = useSetupRun();
  // In the store, so a typed value outlasts leaving Setup.
  const [value, setValue] = useSetupDraft(`value/${toolId}/${step.id}`);
  const what = `${toolId}: ${step.title}`;
  const act = async (request: SetupRequest, button: string) => {
    await runner.run(request, button);
    onChanged();
  };
  // Each button's key is what it sends: "run", "yes", "no", "save", "done", "skipped".
  const apply = (button: string, extra: { answer?: "yes" | "no"; value?: string } = {}) =>
    void act({ command: "apply", tool: toolId, step: step.id, ...extra }, button);
  const mark = (status: "done" | "skipped") =>
    void act({ command: "mark", tool: toolId, step: step.id, status }, status);

  let body: ReactNode = null;
  if (step.terminal) {
    body = <TerminalControls toolId={toolId} stepId={step.id} onCheck={onChanged} />;
  } else if (step.kind === "settings") {
    body = <SettingsForm toolId={toolId} step={step} onSaved={onChanged} />;
  } else if (step.kind === "samples") {
    body = <SamplesPanel toolId={toolId} step={step} onDone={onChanged} />;
  } else if (step.kind === "run" || step.kind === "copy") {
    body = (
      <div className={styles.controls}>
        <Button
          primary={step.status !== "done"}
          onClick={() => apply("run")}
          {...runner.button("run")}
        >
          {step.status === "done" ? "Run again" : "Run"}
        </Button>
        {step.command && <code className={styles.note}>{step.command}</code>}
      </div>
    );
  } else if (step.kind === "confirm") {
    const now = { done: "on (yes)", skipped: "off (no)", failed: "", "": "not chosen" }[
      step.status
    ];
    body = (
      <div className={styles.form}>
        {CONFIRM_NOTES[`${toolId}.${step.id}`] && (
          <p className={styles.note}>{CONFIRM_NOTES[`${toolId}.${step.id}`]}</p>
        )}
        <div className={styles.controls} role="group" aria-label={step.title}>
          <span className={styles.note}>now: {now}</span>
          <Button
            primary={step.status !== "done"}
            onClick={() => apply("yes", { answer: "yes" })}
            {...runner.button("yes")}
          >
            {step.status === "done" && <Mark shape="triangle" />}
            {step.status === "done" && " "}
            Yes
          </Button>
          <Button onClick={() => apply("no", { answer: "no" })} {...runner.button("no")}>
            {step.status === "skipped" && <Mark shape="triangle" />}
            {step.status === "skipped" && " "}
            No
          </Button>
        </div>
      </div>
    );
  } else if (toolId === CONSOLE_ID && step.id === CLAIM_STEP_ID) {
    body = <ClaimLink isClaimDone={step.status === "done"} onMarked={onChanged} />;
  } else if (step.kind === "manual") {
    body = (
      <div className={styles.form}>
        {step.text && <Markdown text={step.text} />}
        <div className={styles.controls}>
          <Button
            primary={step.status !== "done"}
            onClick={() => mark("done")}
            {...runner.button("done")}
          >
            I did this: mark done
          </Button>
        </div>
      </div>
    );
  } else {
    // email or env: one non-secret value (secrets are terminal steps, handled above).
    body = (
      <div className={styles.controls}>
        <input
          className={styles.input}
          aria-label={step.title}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={step.kind === "email" ? "you@gmail.com" : "value"}
        />
        <Button
          primary
          onClick={() => apply("save", { value: value.trim() })}
          {...runner.button("save")}
          disabledReason={value.trim() ? undefined : "type a value first"}
        >
          Save
        </Button>
      </div>
    );
  }

  return (
    <div className={styles.stepBody}>
      {body}
      {step.doc && <StepGuide toolId={toolId} step={step} />}
      {step.optional && step.status !== "skipped" && (
        <div className={styles.controls}>
          <Button onClick={() => mark("skipped")} {...runner.button("skipped")}>
            Skip this step
          </Button>
        </div>
      )}
      <OutputLog run={runner} what={what} />
    </div>
  );
}
