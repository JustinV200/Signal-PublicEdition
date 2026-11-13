// One picked tool: what it is, the programs it still lacks, then each of its
// setup steps with its status and controls (steps/). "Skip this tool" takes
// it out of the picks with `setup choose`.
import { firstJson, parsePrereqs } from "../../../api";
import type { SetupTool } from "../../../api";
import { Button } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import { isChosen } from "../wizardScreens";
import styles from "../setup.module.css";
import { StepRow } from "../steps";
import { useSetupQuery } from "../useSetupQuery";

interface ToolScreenProps {
  tool: SetupTool;
  tools: SetupTool[];
  reload: () => void;
}

/** The tool's header, missing programs and steps. */
export function ToolScreen({ tool, tools, reload }: ToolScreenProps) {
  const runner = useSetupRun();
  const missing = useSetupQuery(
    `prereqs-${tool.id}`,
    { command: "prereqs", tools: [tool.id] },
    (l) => parsePrereqs(firstJson(l)),
  );
  const skipTool = async () => {
    const rest = tools.filter((t) => isChosen(t) && t.id !== tool.id).map((t) => t.id);
    await runner.run({ command: "choose", tools: rest });
    reload();
  };
  const refresh = () => {
    reload();
    missing.reload();
  };
  return (
    <section className={styles.screen}>
      <p className={styles.desc}>{tool.description}</p>
      <p className={styles.note}>
        [{tool.platform}] · status: {tool.status}
        {tool.needs.length > 0 && ` · builds on ${tool.needs.join(", ")}`}
      </p>
      {missing.data?.map((prereq) => (
        <p key={prereq.name} className={styles.note}>
          ! needs {prereq.name}: get it from {prereq.getIt}, then Refresh
        </p>
      ))}
      <ol className={styles.steps}>
        {tool.steps.map((step) => (
          <StepRow key={step.id} toolId={tool.id} step={step} onChanged={refresh} />
        ))}
      </ol>
      <div className={styles.controls}>
        <Button onClick={() => void skipTool()} pending={runner.running}>
          Skip this tool
        </Button>
        <span className={styles.note}>takes it out of your picks; add it back on Pick tools</span>
      </div>
      <OutputLog run={runner} what={`Skipping ${tool.name}`} />
    </section>
  );
}
