// The copytone samples step: add your own writing by pasting it, by naming
// files or folders on this PC (.docx, .pdf, .txt, .md, code), or by picking
// from your sent mail once the mail tool is set up. Each goes through
// `setup samples ...`, which saves the samples and prints the running count.
import { useState } from "react";
import { jsonDocs, parseSampleCount } from "../../../api";
import type { SampleKind, SetupRequest, SetupStep } from "../../../api";
import { Button } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import styles from "../setup.module.css";
import { MailPicker } from "./MailPicker";

const KINDS: readonly SampleKind[] = ["email", "writing", "message", "code"];

interface SamplesPanelProps {
  toolId: string;
  step: SetupStep;
  /** Called after "Done adding" marks the step done. */
  onDone: () => void;
}

/** Paste, files and sent-mail controls with the running count. */
export function SamplesPanel({ toolId, step, onDone }: SamplesPanelProps) {
  const runner = useSetupRun();
  const [kind, setKind] = useState<SampleKind>("writing");
  const [pasted, setPasted] = useState("");
  const [paths, setPaths] = useState("");
  const [count, setCount] = useState<string | null>(null);

  const send = async (request: SetupRequest) => {
    const result = await runner.run(request);
    const last = result ? jsonDocs(result.lines).at(-1) : undefined;
    if (last === undefined) return false;
    const { samples, target } = parseSampleCount(last);
    setCount(`${samples} saved (aim for ${target})`);
    return result?.exit === 0;
  };
  const savePaste = async () => {
    if (await send({ command: "samples", action: "paste", kind, text: pasted })) setPasted("");
  };
  const addFiles = async () => {
    const list = paths
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    if (await send({ command: "samples", action: "files", kind, paths: list })) setPaths("");
  };
  const finish = async () => {
    const result = await runner.run({
      command: "mark",
      tool: toolId,
      step: step.id,
      status: "done",
    });
    if (result?.exit === 0) onDone();
  };

  return (
    <div className={styles.form}>
      <div className={styles.controls}>
        <span className={styles.note}>
          {count ?? "aim for 5 to 15 samples of your own writing"}
        </span>
        <Button onClick={() => void send({ command: "samples", action: "count" })}>Count</Button>
        <label className={styles.check}>
          kind{" "}
          <select
            className={styles.input}
            value={kind}
            onChange={(event) => setKind(event.target.value as SampleKind)}
          >
            {KINDS.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
      </div>
      <label className={styles.fieldLabel} htmlFor="sample-paste">
        Paste something you wrote
      </label>
      <textarea
        id="sample-paste"
        className={styles.area}
        rows={5}
        value={pasted}
        onChange={(event) => setPasted(event.target.value)}
      />
      <div className={styles.controls}>
        <Button
          onClick={() => void savePaste()}
          pending={runner.running}
          disabledReason={pasted.trim() ? undefined : "paste some text first"}
        >
          Save pasted text
        </Button>
      </div>
      <label className={styles.fieldLabel} htmlFor="sample-paths">
        Files or folders on this PC, one per line (full paths)
      </label>
      <textarea
        id="sample-paths"
        className={styles.area}
        rows={3}
        value={paths}
        onChange={(event) => setPaths(event.target.value)}
      />
      <div className={styles.controls}>
        <Button
          onClick={() => void addFiles()}
          pending={runner.running}
          disabledReason={paths.trim() ? undefined : "give a path first"}
        >
          Add files
        </Button>
      </div>
      <MailPicker onKept={(words) => setCount(words)} />
      <div className={styles.controls}>
        <Button primary onClick={() => void finish()} pending={runner.running}>
          Done adding samples
        </Button>
      </div>
      <OutputLog run={runner} what={`${toolId}: ${step.title}`} />
    </div>
  );
}
