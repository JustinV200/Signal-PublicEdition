// The controls for one step, chosen by its kind (tools/setup registry):
// run/copy -> Run; confirm -> Yes / No (e.g. the browser auto-approve toggle);
// manual -> the instructions and Mark done; email/env -> a field and Save;
// settings -> the schema form; samples -> the samples panel. A step that needs
// the owner's own terminal gets Open a terminal instead. Optional steps can be
// skipped. Each command's live output and any failure show below.
import { useState } from "react";
import type { ReactNode } from "react";
import type { SetupRequest, SetupStep } from "../../../api";
import { Markdown } from "../../../markdown";
import { Button } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import { SamplesPanel } from "../samples";
import { SettingsForm } from "../settings";
import styles from "../setup.module.css";
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
  const [value, setValue] = useState("");
  const what = `${toolId}: ${step.title}`;
  const act = async (request: SetupRequest) => {
    await runner.run(request);
    onChanged();
  };
  const apply = (extra: { answer?: "yes" | "no"; value?: string } = {}) =>
    void act({ command: "apply", tool: toolId, step: step.id, ...extra });
  const mark = (status: "done" | "skipped") =>
    void act({ command: "mark", tool: toolId, step: step.id, status });
  const busy = runner.running;

  let body: ReactNode = null;
  if (step.terminal) {
    body = <TerminalControls toolId={toolId} onMarkDone={() => mark("done")} busy={busy} />;
  } else if (step.kind === "settings") {
    body = <SettingsForm toolId={toolId} step={step} onSaved={onChanged} />;
  } else if (step.kind === "samples") {
    body = <SamplesPanel toolId={toolId} step={step} onDone={onChanged} />;
  } else if (step.kind === "run" || step.kind === "copy") {
    body = (
      <div className={styles.controls}>
        <Button primary={step.status !== "done"} onClick={() => apply()} pending={busy}>
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
            onClick={() => apply({ answer: "yes" })}
            pending={busy}
          >
            {step.status === "done" ? "▸ Yes" : "Yes"}
          </Button>
          <Button onClick={() => apply({ answer: "no" })} pending={busy}>
            {step.status === "skipped" ? "▸ No" : "No"}
          </Button>
        </div>
      </div>
    );
  } else if (step.kind === "manual") {
    body = (
      <div className={styles.form}>
        {step.text && <Markdown text={step.text} />}
        {step.doc && (
          <p className={styles.note}>
            Details: <code>{step.doc}</code>
          </p>
        )}
        <div className={styles.controls}>
          <Button primary={step.status !== "done"} onClick={() => mark("done")} pending={busy}>
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
          onClick={() => apply({ value: value.trim() })}
          pending={busy}
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
      {step.optional && step.status !== "skipped" && (
        <div className={styles.controls}>
          <Button onClick={() => mark("skipped")} pending={busy}>
            Skip this step
          </Button>
        </div>
      )}
      <OutputLog run={runner} what={what} />
    </div>
  );
}
