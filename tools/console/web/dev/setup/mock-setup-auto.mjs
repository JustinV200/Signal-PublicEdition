// The mock `setup auto` (tools/setup cli/auto.py): runs each picked tool's
// automatic steps in registry order with the mock's fake step runs, stops a
// tool at its first required step that needs the owner (or fails), and ends
// with the same JSON: {ran, stopped, messages}. Exit 0, 1 (a step failed) or 3
// (a step needs the owner). Used by mock-setup-cli.mjs, which passes in its
// live tools and its step runner, so a batch changes the mock like clicks do.

const UNATTENDED_KINDS = ["run", "copy"];
const SETTLED = ["done", "skipped"];
const NEEDS_INPUT = "needs_input";
const ALL_DONE = "Every required step of your picks is done; optional steps wait for your click.";
const NONE_USABLE = "Nothing ran: none of the named tools is picked and can run on this OS.";
const NOTHING_PICKED = "Nothing ran: nothing is picked yet.";
// cli/auto.py's exit codes: a step failed, none of the named tools can run, a step needs you.
const EXIT_FAILED = 1;
const EXIT_NONE_USABLE = 2;
const EXIT_NEEDS_YOU = 3;

/** A required run or copy step that needs nobody (registry.Step.is_automatic). */
export const isAutomatic = (step) =>
  UNATTENDED_KINDS.includes(step.kind) && !step.optional && !step.terminal && !step.opens_browser;

const stopAt = (tool, step, reason) => ({
  tool: tool.id,
  step: step.id,
  title: step.title,
  reason,
});

/** One tool's automatic steps; the stop where it ended early, or null. */
function runTool(tool, { runStep, setStep }, out) {
  for (const step of tool.steps) {
    if (step.optional || SETTLED.includes(step.status)) continue;
    if (!isAutomatic(step)) return stopAt(tool, step, "needs_you");
    out.lines.push("", `== ${tool.name}: ${step.title} ==`);
    const { status, messages, output = [] } = runStep(tool, step, {});
    out.lines.push(...messages, ...output);
    if (status !== NEEDS_INPUT) setStep(tool, step, status);
    out.ran.push({ tool: tool.id, step: step.id, status });
    if (status !== "done") return stopAt(tool, step, status === "failed" ? "failed" : "needs_you");
  }
  return null;
}

/** A stop in words, as cli/auto.py says it. */
function stopWords(stop, tools) {
  const name = tools.find((tool) => tool.id === stop.tool)?.name ?? stop.tool;
  return stop.reason === "failed"
    ? `Failed: ${name}, '${stop.title}' (see its output above).`
    : `Needs you: ${name}, '${stop.title}'.`;
}

/**
 * `setup auto [ids]`: the picks' automatic steps (only `ids`' when given, and only picked ones).
 *
 * @param {object[]} tools The mock's live tools (ids already checked).
 * @param {string[]} ids The tools asked for; empty for every pick.
 * @param {{runStep: Function, setStep: Function}} helpers The CLI mock's step runner and recorder.
 * @returns {{lines: string[], exit: number}} The output lines and the exit code.
 */
export function runAuto(tools, ids, helpers) {
  const out = { lines: [], ran: [] };
  const stops = [];
  let ranTools = 0;
  for (const tool of tools) {
    if (ids.length && !ids.includes(tool.id)) continue;
    if (!tool.picked) {
      if (ids.length) out.lines.push(`${tool.name} isn't picked, so nothing of it runs.`);
      continue;
    }
    ranTools += 1;
    const stop = runTool(tool, helpers, out);
    if (stop) stops.push(stop);
  }
  const idle = ids.length ? NONE_USABLE : NOTHING_PICKED;
  const messages = stops.length
    ? stops.map((stop) => stopWords(stop, tools))
    : [ranTools ? ALL_DONE : idle];
  const result = { ran: out.ran, stopped: stops, messages };
  let exit = stops.length ? EXIT_NEEDS_YOU : 0;
  if (stops.some((stop) => stop.reason === "failed")) exit = EXIT_FAILED;
  if (ids.length && !ranTools) exit = EXIT_NONE_USABLE;
  return { lines: [...out.lines, ...JSON.stringify(result, null, 2).split("\n")], exit };
}
