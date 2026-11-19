// One picked tool: what it is, the failing check when a System Fix opened it
// (health's CheckBanner: why the page is open while every step reads done),
// a note when setup has no record of it and found it already set up (why it
// reads done above steps that all read to do), a banner while it's set up but
// not yet in Claude Code's config (with Add to Claude Code), the programs it still lacks
// (where to get each, a URL there a link), then each of its setup steps with
// its status and controls (steps/). "Run the automatic steps" runs its
// required run and copy steps that need nobody (`setup auto <tool>`) and
// names the step it stopped at. "Skip this tool" takes it out of the picks
// with `setup choose`; a tool found already set up stays as it is, and its
// note says so.
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

// A tool set up by hand reads done, yet setup never ran its steps: say so above them,
// what the first step result does (the CLI then starts its record as a finished one),
// and that its entries stay the owner's (`setup wire` takes out only what it added).
const DETECTED_NOTE =
  "Found already set up, so setup didn't run the steps below and they read to do. " +
  "Run, mark or skip one and setup takes this tool on as finished: its required steps " +
  "read done. The entries you made for it in Claude Code stay as they are: setup only " +
  "takes out or replaces what it added itself.";
// What Skip this tool does: a skipped tool loses what setup added for it at the next
// Add to Claude Code, and setup added nothing for one it only found.
const SKIP_NOTE =
  "takes it out of your picks (add it back on Pick tools); the next Add to Claude Code " +
  "takes out what setup added for it";
const SKIP_DETECTED_NOTE =
  "takes it out of your picks; it stays set up and in Claude Code as you made it";

interface ToolScreenProps {
  tool: SetupTool;
  tools: SetupTool[];
  /** The wizard's wire runner, so Summary knows a wire worked. */
  wiring: AddToClaude;
  reload: () => void;
}

/** The tool's header, the found-already note, the not-added banner, missing programs and steps. */
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
      {tool.detected && <p className={styles.note}>{DETECTED_NOTE}</p>}
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
          <Button
            // Not the page's main action on a tool found already set up: it works as it is.
            primary={hasAutomaticLeft && !tool.detected}
            onClick={() => void runAutomatic()}
            {...auto.button()}
          >
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
        <span className={styles.note}>{tool.detected ? SKIP_DETECTED_NOTE : SKIP_NOTE}</span>
      </div>
      <OutputLog run={runner} what={`Skipping ${tool.name}`} />
    </section>
  );
}
