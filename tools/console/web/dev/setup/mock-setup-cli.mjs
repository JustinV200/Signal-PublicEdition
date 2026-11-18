// The mock setup CLI: answers each wizard command from a live copy of
// mock-setup-data.mjs's registry, printing what tools/setup's commands print
// (cli/agent.py, cli/main.py): indented JSON or plain lines, and the exit code
// (0 done, 1 failed, 2 bad id, 3 needs you). choose, mark, apply, auto, wire,
// config --set and samples change the copy, so the wizard moves on like the real one until
// the mock restarts. Settings come from mock-setup-config.mjs and samples from
// mock-setup-samples.mjs, doc's made-up guide from mock-setup-doc.mjs,
// plan's lines from mock-setup-plan.mjs, status's health rows from
// mock-setup-checks.mjs, and the --setup-done and --setup-all starts from
// mock-setup-entries.mjs.
// verify is no page command (setup_cli/requests.py).
// Used by mock-setup.mjs, which streams the answer.
import {
  createConfigFile,
  hasSettings,
  listSettings,
  placeholdersLeft,
  setSettings,
} from "./mock-setup-config.mjs";
import { freshTools, INTRO, MISSING_PREREQS, TOUR } from "./mock-setup-data.mjs";
import { withAllPicked, withPicksDone } from "./mock-setup-entries.mjs";
import { samplesDocs } from "./mock-setup-samples.mjs";
import { isAutomatic, runAuto } from "./mock-setup-auto.mjs";
import { healthRows } from "./mock-setup-checks.mjs";
import { guideAnswer } from "./mock-setup-doc.mjs";
import { planLines } from "./mock-setup-plan.mjs";

// The live registry copy, made on the first command (a first run's with --setup-fresh).
let tools = null;
const NEEDS_INPUT = "needs_input";
const EXIT_FAILED = 1;
const EXIT_BAD_ID = 2;
const EXIT_NEEDS_YOU = 3;
const EXIT_FOR_STATUS = { failed: EXIT_FAILED, [NEEDS_INPUT]: EXIT_NEEDS_YOU };
// What a run step's program prints before the CLI's JSON (uv sync's lines).
const INSTALL_OUTPUT = [
  "Resolved 38 packages in 12ms",
  "Prepared 2 packages in 1.40s",
  "Installed 2 packages in 31ms",
  " + example-package==1.0.0",
];

/** `data` as the CLI prints it (json.dumps with indent=2), one output line each. */
const printed = (data) => JSON.stringify(data, null, 2).split("\n");

/** A finished command: the lines it printed and its exit code. */
const answer = (lines, exit = 0) => ({ lines, exit });

/** `setup: error: …` with exit 2, as main.py reports an unknown tool or step. */
const badId = (why) => answer([`setup: error: ${why}`], EXIT_BAD_ID);

const findTool = (id) => tools.find((tool) => tool.id === id);
const unknownTool = (id) =>
  `unknown tool '${id}'; choose from: ${tools.map((tool) => tool.id).join(", ")}`;

/** The whole tool's status, as progress.tool_status works it out: done, skipped, failed, started or "". */
function toolStatus(tool) {
  if (!tool.touched) return "";
  if (tool.skipped) return "skipped";
  // Only optional steps (copytone): not done until one of them is done or skipped.
  const settled = tool.steps.some((step) => ["done", "skipped"].includes(step.status));
  if (tool.steps.every((step) => step.optional) && !settled) return "started";
  // An optional settings step the owner took counts too: placeholders left mean not done.
  const counted = tool.steps.filter(
    (step) =>
      !step.optional || (step.kind === "settings" && !["", "skipped"].includes(step.status)),
  );
  if (counted.every((step) => step.status === "done")) return "done";
  return counted.some((step) => step.status === "failed") ? "failed" : "started";
}

/** Claude Code's config holds the tool, which only counts once it's done (wiring.wired_tools). */
const isWired = (tool) => tool.wired && toolStatus(tool) === "done";

/** Records a step's result; running any step un-skips its tool (progress.set_step). */
function setStep(tool, step, status) {
  step.status = status;
  tool.touched = true;
  tool.skipped = false;
}

function listTools() {
  return answer(
    printed(
      tools.map((tool) => ({
        id: tool.id,
        name: tool.name,
        description: tool.description,
        group: tool.group,
        cost: tool.cost,
        platform: tool.platform,
        supported_here: true, // the mock stands for a Windows PC, where every mock tool runs
        status: toolStatus(tool) || "not set up",
        picked: tool.picked,
        wired: isWired(tool),
        needs: tool.needs,
        prereqs: tool.prereqs,
        steps: tool.steps.map((step) => ({ ...step, automatic: isAutomatic(step) })),
      })),
    ),
  );
}

function prereqs(ids) {
  const unknown = ids.find((id) => !findTool(id));
  if (unknown) return badId(unknownTool(unknown));
  const missing = MISSING_PREREQS.filter(
    (prereq) => ids.length === 0 || prereq.usedBy.some((id) => ids.includes(id)),
  );
  return answer(printed(missing.map(({ name, get_it }) => ({ name, get_it }))));
}

function choose(ids) {
  const unknown = ids.find((id) => !findTool(id));
  if (unknown) return badId(unknownTool(unknown));
  for (const tool of tools) {
    tool.touched = true;
    tool.picked = ids.includes(tool.id);
    tool.skipped = !tool.picked;
  }
  return answer(printed({ chosen: ids }));
}

/** `setup wire --yes`: Claude Code's config now holds exactly the finished tools. */
function wire() {
  for (const tool of tools) tool.wired = toolStatus(tool) === "done";
  return answer(printed({ written: [".mcp.json", ".claude/settings.local.json"], notes: [] }));
}

/** The tool and step a request names, or `error` words for an unknown one. */
function findStep(toolId, stepId) {
  const tool = findTool(toolId);
  if (!tool) return { error: unknownTool(toolId) };
  const step = tool.steps.find((candidate) => candidate.id === stepId);
  return step ? { tool, step } : { error: `${toolId} has no step '${stepId}'` };
}

function mark({ tool: toolId, step: stepId, status }) {
  const { tool, step, error } = findStep(toolId, stepId);
  if (error) return badId(error);
  setStep(tool, step, status);
  return answer(printed({ tool: toolId, step: stepId, status }));
}

// Steps whose fake run doesn't just work, keyed `<tool>.<step>`; null means it does.
const OUTCOMES = {
  // Docker Desktop is in MISSING_PREREQS, so its step fails before running anything.
  "browser.docker": () => ({
    status: "failed",
    messages: [`Missing: ${MISSING_PREREQS[0].name} (${MISSING_PREREQS[0].get_it})`],
  }),
  // The sign-in command fills in {email}, so it needs the email step done first.
  "mail.signin": () =>
    findStep("mail", "email").step.status === "done"
      ? null
      : { status: NEEDS_INPUT, messages: ["Answer the 'email' step first."] },
};

/** A step's fake run by kind (steps/run.py): {status, messages, output?}. */
function runStep(tool, step, { answer: reply, value }) {
  const special = OUTCOMES[`${tool.id}.${step.id}`]?.();
  if (special) return special;
  const replied = reply ? (reply === "yes" ? "done" : "skipped") : NEEDS_INPUT;
  if (step.kind === "confirm") return { status: replied, messages: [] };
  if (step.kind === "manual") return { status: replied, messages: [step.text] };
  if (step.kind === "email" || step.kind === "env")
    return { status: value ? "done" : NEEDS_INPUT, messages: [] };
  if (step.kind === "copy") return { status: "done", messages: ["Copied the example config."] };
  if (step.kind === "settings") return runSettingsStep(tool, step);
  return { status: "done", output: INSTALL_OUTPUT, messages: [`$ ${step.command}`] };
}

/** A settings step (steps/settings_step.py): done once no placeholder is left in its group. */
function runSettingsStep(tool, step) {
  const file = createConfigFile(tool.id);
  const messages = file ? [`Created ${file} from its example.`] : [];
  const left = placeholdersLeft(tool.id, step.group);
  if (!left.length) return { status: "done", messages };
  messages.push(
    `Placeholders left: ${left.join(", ")}`,
    `Ask the user for each value, then run: setup config ${tool.id} --set id=value`,
  );
  return { status: NEEDS_INPUT, messages };
}

/** `setup config <tool>`: the rows (--list), or set values and re-check the settings steps. */
function config({ tool: toolId, set: values }) {
  const tool = findTool(toolId);
  if (!tool) return badId(unknownTool(toolId));
  if (!hasSettings(toolId)) return badId(`${toolId} has no settings`);
  if (!values) return answer(printed(listSettings(toolId)));
  const { set, errors, groups } = setSettings(toolId, values);
  const messages = [];
  const settingsSteps = tool.steps.filter(
    (step) => step.kind === "settings" && groups.has(step.group) && step.status !== "skipped",
  );
  for (const step of settingsSteps) {
    const result = runSettingsStep(tool, step);
    messages.push(...result.messages);
    if (result.status !== NEEDS_INPUT) setStep(tool, step, result.status);
  }
  // Placeholders in every group whose settings step isn't skipped (settings.tool_leftovers).
  const leftIds = tool.steps
    .filter((step) => step.kind === "settings" && step.status !== "skipped")
    .flatMap((step) => placeholdersLeft(toolId, step.group));
  const result = { set, errors, reruns: {}, placeholders_left: leftIds, messages };
  return answer(printed(result), Object.keys(errors).length ? EXIT_FAILED : 0);
}

function apply(request) {
  const { tool, step, error } = findStep(request.tool, request.step);
  if (error) return badId(error);
  if (step.terminal || step.kind === "samples") {
    const how = step.kind === "samples" ? "setup samples ..." : `setup step ${tool.id} ${step.id}`;
    return answer(printed({ status: "needs_terminal", run_in_user_terminal: how }), EXIT_NEEDS_YOU);
  }
  const { status, messages, output = [] } = runStep(tool, step, request);
  if (status !== NEEDS_INPUT) setStep(tool, step, status);
  const result = { tool: tool.id, step: step.id, status, messages };
  return answer([...output, ...printed(result)], EXIT_FOR_STATUS[status] ?? 0);
}

/** `setup auto`: the picks' automatic steps, through the same fake step runs as apply. */
function auto(ids) {
  const unknown = ids.find((id) => !findTool(id));
  return unknown ? badId(unknownTool(unknown)) : runAuto(tools, ids, { runStep, setStep });
}

/** The registry copy the mock starts from, by its start switch. */
function startTools({ isFirstRun, isAllDone, isAllPicked }) {
  if (isAllDone) return withPicksDone(freshTools());
  if (isAllPicked) return withAllPicked(freshTools());
  return freshTools({ isFirstRun });
}

/**
 * What `setup <command>` prints for a wizard request.
 *
 * @param {object} request The page's request body, its shape already checked by mock-setup.mjs.
 * @param {{isFirstRun?: boolean, isAllDone?: boolean, isAllPicked?: boolean}} options
 *   isFirstRun: start the live copy from a first run (--setup-fresh); isAllDone: with every
 *   pick finished (--setup-done); isAllPicked: with every tool picked (--setup-all); only
 *   the first command's choice counts.
 * @returns {{lines: string[], exit: number}} The output lines and the exit code.
 */
export function runCommand(
  request,
  { isFirstRun = false, isAllDone = false, isAllPicked = false } = {},
) {
  tools ??= startTools({ isFirstRun, isAllDone, isAllPicked });
  const commands = {
    intro: () => answer([INTRO]),
    doc: () => guideAnswer(findStep(request.tool, request.step), badId),
    list: listTools,
    prereqs: () => prereqs(request.tools ?? []),
    plan: () => answer(planLines(tools.filter((tool) => toolStatus(tool) === "done"))),
    status: () => answer(printed(healthRows(tools, { toolStatus, isWired }))),
    tour: () => answer(printed(TOUR)),
    choose: () => choose(request.tools ?? []),
    mark: () => mark(request),
    apply: () => apply(request),
    auto: () => auto(request.tools ?? []),
    wire,
    config: () => config(request),
    samples: () => answer(samplesDocs(request).flatMap(printed)),
  };
  const command = commands[request.command];
  return command
    ? command()
    : answer([`The mock doesn't run setup ${request.command}.`], EXIT_FAILED);
}
