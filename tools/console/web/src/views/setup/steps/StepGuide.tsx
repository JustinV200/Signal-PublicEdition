// A step's guide under its controls: the file its registry `doc` names, read
// with `setup doc <tool> <step>` only once the owner opens it (collapsed by
// default), and shown through the shared Markdown component, so raw HTML stays
// text and only http(s) links work. A guide this copy doesn't ship comes back
// as the CLI's one plain sentence (exit 1), shown as a note.
import { useState } from "react";
import type { SetupStep } from "../../../api";
import { Markdown } from "../../../markdown";
import { Mark } from "../../../ui";
import styles from "../setup.module.css";
import { useSetupQuery } from "../useSetupQuery";
import guide from "./guide.module.css";

/** What `setup doc` gave: the guide's text, or (when not found) the CLI's sentence. */
interface GuideAnswer {
  text: string;
  isFound: boolean;
}

interface StepGuideProps {
  toolId: string;
  step: SetupStep;
}

/** The opened guide: read once it mounts, then Markdown or the reason there's none. */
function GuideBody({ toolId, step }: StepGuideProps) {
  const answer = useSetupQuery<GuideAnswer>(
    `doc-${toolId}-${step.id}`,
    { command: "doc", tool: toolId, step: step.id },
    (lines, exit) => ({ text: lines.join("\n").trim(), isFound: exit === 0 }),
  );
  if (answer.error)
    return (
      <p className={styles.problem}>
        <Mark shape="cross" /> Couldn't read the guide: {answer.error}
      </p>
    );
  if (!answer.data) return <p className={styles.note}>… reading the guide</p>;
  if (!answer.data.isFound)
    return <p className={styles.note}>! {answer.data.text || "No guide for this step."}</p>;
  return (
    <div className={guide.body}>
      <Markdown text={answer.data.text} />
    </div>
  );
}

/** "Guide: <file>", collapsed; the native marker's turn shows open or shut. */
export function StepGuide({ toolId, step }: StepGuideProps) {
  const [isOpen, setOpen] = useState(false);
  return (
    <details className={styles.disclosure} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className={styles.note}>
        Guide: <code>{step.doc}</code>
      </summary>
      {isOpen && <GuideBody toolId={toolId} step={step} />}
    </details>
  );
}
