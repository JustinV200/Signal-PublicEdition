// One picked tool: what it is, the failing check when a System Fix opened it
// (health's CheckBanner: why the page is open while every step reads done),
// a banner while it's set up but not yet in
// Claude Code's config (with Add to Claude Code), the programs it still lacks
// (where to get each, a URL there a link), then each of its setup steps with
// its status and controls (steps/). "Run the automatic steps" runs its
// required run and copy steps that need nobody (`setup auto <tool>`) and
// names the step it stopped at. "Skip this tool" takes it out of the picks
// with `setup choose`.
import { firstJson, parsePrereqs } from "../../../api";
import type { SetupTool } from "../../../api";
import { LinkedText } from "../../../markdown";
import { useStore } from "../../../state";
import { Button, Mark } from "../../../ui";
import { CheckBanner, NOT_WIRED_LOOK } from "../health";
import { ADD_TO_CLAUDE, AddResult, AutoStops, OutputLog, useSetupRun } from "../run";
import type { AddToClaude } from "../run";
import { isChosen } from "../wizardScreens";
import styles from "../setup.module.css";
import { StepRow } from "../steps";
import { useSetupQuery } from "../useSetupQuery";

interface ToolScreenProps {
  tool: SetupTool;
  tools: SetupTool[];
  /** The wizard's wire runner, so Summary knows a wire worked. */
  wiring: AddToClaude;
  reload: () => void;
}

/** The tool's header, the not-added banner, missing programs and steps. */
export function ToolScreen({ tool, tools, wiring, reload }: ToolScreenProps) {
  const { state } = useStore();
  const check = state.setupCheck?.id === tool.id ? state.setupCheck : null;
  const runner = useSetupRun();
  const auto = useSetupRun();
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
  const runAutomatic = async () => {
    await auto.run({ command: "auto", tools: [tool.id] });
    refresh();
  };
  const hasAutomaticLeft = tool.steps.some(
    (step) => step.automatic && step.status !== "done" && step.status !== "skipped",
  );
  return (
    <section className={styles.screen}>
      {check && <CheckBanner row={check} />}
      <p className={styles.desc}>{tool.description}</p>
      <p className={styles.note}>
        [{tool.platform}] · status: {tool.status}
        {tool.needs.length > 0 && ` · builds on ${tool.needs.join(", ")}`}
      </p>
      {tool.status === "done" && !tool.wired && !wiring.added && (
        <div className={`panel ${styles.controls} ${styles.banner}`}>
          <strong>
            <Mark shape={NOT_WIRED_LOOK.mark} /> {NOT_WIRED_LOOK.label}
          </strong>
          <Button
            primary
            onClick={() => void wiring.add().then(reload)}
            {...wiring.runner.button()}
          >
            {ADD_TO_CLAUDE}
          </Button>
        </div>
      )}
      <AddResult wiring={wiring} />
      {missing.data?.map((prereq) => (
        <p key={prereq.name} className={styles.note}>
          ! needs {prereq.name}: get it from <LinkedText text={prereq.getIt} />, then Refresh
        </p>
      ))}
      {(hasAutomaticLeft || auto.exit !== null) && (
        <div className={styles.controls}>
          <Button primary={hasAutomaticLeft} onClick={() => void runAutomatic()} {...auto.button()}>
            Run the automatic steps
          </Button>
          <span className={styles.note}>
            its required installs, one after another; stops at the first step that needs you
          </span>
        </div>
      )}
      <OutputLog run={auto} what={`${tool.name}: the automatic steps`} hasStopsBelow />
      <AutoStops run={auto} tools={tools} />
      <ol className={styles.steps}>
        {tool.steps.map((step) => (
          <StepRow key={step.id} toolId={tool.id} step={step} onChanged={refresh} />
        ))}
      </ol>
      <div className={styles.controls}>
        <Button onClick={() => void skipTool()} {...runner.button()}>
          Skip this tool
        </Button>
        <span className={styles.note}>takes it out of your picks; add it back on Pick tools</span>
      </div>
      <OutputLog run={runner} what={`Skipping ${tool.name}`} />
    </section>
  );
}
