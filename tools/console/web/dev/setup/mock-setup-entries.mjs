// The mock registry's building blocks: a tool entry and its steps with
// tools/setup's defaults (each tool's Pick tools group and cost tag too), and
// the two other starts: a fresh checkout (--setup-fresh: nothing picked, only
// the console built) and --setup-done (every step of every pick done, so no
// pick is unfinished and the status line shows no Setup tab until Setup is
// opened; untouched and skipped tools stay as they are), and --setup-all
// (every tool picked, so the wizard's strip and tools list are at their
// longest). Used by
// mock-setup-data.mjs, which lists the tools, and mock-setup-cli.mjs.

// Each tool's Pick tools group and cost tag, as in tools/setup's registry.
const PICK_INFO = {
  brief: ["Core", "1 min"],
  console: ["Core", "5 min, Node.js and Edge"],
  audiohub: ["Hardware", "large download, speakers"],
  copytone: ["Everyday", "10 min, your writing samples"],
  browser: ["Everyday", "5 min, Edge"],
  vault: ["Everyday", "2 min, Windows Hello"],
  mail: ["Everyday", "15 min, Google account"],
  calendar: ["Everyday", "5 min, after Gmail"],
  whiteboard: ["Hardware", "needs a projector and webcam"],
  sleepmode: ["Hardware", "1 min"],
  sessions: ["Extras", "1 min"],
};

/** A registry step with tools/setup's defaults; `status` is its saved progress. */
export const step = (id, title, kind, extra = {}) => ({
  id,
  title,
  kind,
  optional: false,
  default: true,
  terminal: false,
  text: "",
  doc: "",
  group: "",
  command: "",
  status: "",
  ...extra,
});

export const install = (toolId, status = "done") =>
  step("install", "Install", "run", {
    command: `uv sync --project tools/${toolId} --frozen`,
    status,
  });

/**
 * A registry tool with its progress. `touched` is false for a tool setup never
 * recorded ("not set up"); `picked` is whether it's in progress `chosen` (by
 * default unless skipped or untouched); `wired` is whether Claude Code's config
 * holds it (only counts once it's done); `mcp`, `allow` and `hooks` are what
 * `setup plan` wires for it once it's done. Only mock-setup-cli.mjs reads those.
 */
export function tool(id, name, description, extra, steps) {
  const [group, cost] = PICK_INFO[id];
  const base = {
    id,
    name,
    description,
    group,
    cost,
    platform: "Windows",
    needs: [],
    prereqs: ["uv"],
    touched: true,
    skipped: false,
    wired: true,
    mcp: [],
    allow: [],
    hooks: [],
    ...extra,
    steps,
  };
  return { picked: base.touched && !base.skipped, ...base };
}

// The console steps `setup ui` runs before the window opens (cli/ui_launch.py BOOTSTRAP_STEPS).
const BOOTSTRAP_STEPS = ["install", "web-deps", "web-build"];

/** `entry` on a fresh checkout: nothing picked or wired, only the console's build steps done. */
export function asFirstRun(entry) {
  const isConsole = entry.id === "console";
  const steps = entry.steps.map((step) => ({
    ...step,
    status: isConsole && BOOTSTRAP_STEPS.includes(step.id) ? "done" : "",
  }));
  return { ...entry, touched: isConsole, skipped: false, picked: false, wired: false, steps };
}

/**
 * `tools` with every picked tool finished.
 *
 * @param {object[]} tools The mock registry with its progress (mock-setup-data.mjs freshTools).
 * @returns {object[]} New tool objects; `tools` is left as it was.
 */
export function withPicksDone(tools) {
  return tools.map((tool) =>
    tool.picked
      ? { ...tool, steps: tool.steps.map((step) => ({ ...step, status: "done" })) }
      : tool,
  );
}

/**
 * `tools` with every tool picked (none skipped), each keeping its step progress.
 *
 * @param {object[]} tools The mock registry with its progress (mock-setup-data.mjs freshTools).
 * @returns {object[]} New tool objects; `tools` is left as it was.
 */
export function withAllPicked(tools) {
  return tools.map((tool) => ({ ...tool, picked: true, skipped: false, touched: true }));
}
