// The mock backend's setup routes, like signal_console.server.routes.setup:
// POST /api/setup/run checks the request's shape (400), refuses a second
// command that writes while one runs (409), then streams what the mock setup
// CLI (mock-setup-cli.mjs) printed as NDJSON: {"line"} per output line, then
// {"exit"}. A step's run (apply, auto) streams slowly, so "… running" shows.
// POST /api/setup/terminal checks its tool and step ids and answers ok without
// opening anything. Used by
// mock-server.mjs; `setupFail` (its --setup-fail flag) makes `list` and
// `status` fail the way a broken .setup/progress.json does, `setupFresh`
// (--setup-fresh) starts from a first run: nothing picked, only the console
// built, `setupDone` (--setup-done) starts with every pick finished, and
// `setupAll` (--setup-all) with every tool picked, mid-setup.
import { runCommand } from "./mock-setup-cli.mjs";

const RUN_PATH = "/api/setup/run";
const TERMINAL_PATH = "/api/setup/terminal";
// Commands that only read, which run beside anything (setup_cli/requests.py READ_ONLY).
const READ_ONLY = new Set(["intro", "list", "plan", "status", "tour", "prereqs", "doc"]);
const WRITING = new Set(["wire", "choose", "auto", "apply", "mark", "config", "samples"]);
// Tool and step ids, as setup_cli/requests.py checks them.
const REGISTRY_ID = /^[a-z0-9][a-z0-9-]{0,40}$/;
const SAMPLE_ACTIONS = ["files", "paste", "mail", "keep", "count"];
const SAMPLE_KINDS = ["email", "writing", "message", "code"];
// How long a step's run waits before each line it prints.
const STEP_LINE_MS = 250;
const BUSY = "another setup step is still running; wait for it to finish";
// The commands --setup-fail breaks: the tool lists of Setup and System's tools list.
const FAILING_COMMANDS = new Set(["list", "status"]);
// The CLI's exit code for a failed command (cli/agent.py), as a Python traceback gives.
const EXIT_FAILED = 1;
// The end of the traceback a corrupt progress file gives (json.loads in progress.load).
const BROKEN_PROGRESS = [
  "Traceback (most recent call last):",
  '  File "tools/setup/src/signal_setup/progress.py", line 23, in load',
  "json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
];

// True while a command that writes is streaming (the real server's one-at-a-time lock).
let isWriting = false;

const isId = (value) => typeof value === "string" && REGISTRY_ID.test(value);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const toolListError = ({ tools = [] }) =>
  Array.isArray(tools) && tools.every(isId) ? null : "tools must be a list of tool ids";

function stepIdsError({ tool, step }) {
  if (!isId(tool)) return "tool must be a tool or step id";
  return isId(step) ? null : "step must be a tool or step id";
}

function configError({ tool, set: values }) {
  if (!isId(tool)) return "tool must be a tool or step id";
  if (values == null) return null; // no `set`: list the settings
  const isPairs =
    typeof values === "object" &&
    !Array.isArray(values) &&
    Object.keys(values).length > 0 &&
    Object.values(values).every((value) => typeof value === "string");
  return isPairs ? null : "set must be an object of setting id to value";
}

function samplesError({ action, kind = "writing", paths, numbers, text }) {
  if (!SAMPLE_ACTIONS.includes(action) || !SAMPLE_KINDS.includes(kind))
    return "unknown samples action or kind";
  const isPath = (path) => typeof path === "string" && path.trim() && !path.startsWith("-");
  if (action === "files" && !(Array.isArray(paths) && paths.length && paths.every(isPath)))
    return "paths must list files or folders, none starting with '-'";
  const isCount = (number) => Number.isInteger(number) && number > 0;
  if (action === "keep" && !(Array.isArray(numbers) && numbers.every(isCount)))
    return "numbers must be a list of positive whole numbers";
  if (action === "paste" && !(typeof text === "string" && text.trim()))
    return "text must hold some writing";
  return null;
}

// Each command's own fields, checked as setup_cli/requests.py does (null: fine).
const FIELD_CHECKS = {
  prereqs: toolListError,
  choose: toolListError,
  auto: toolListError,
  apply: (body) =>
    stepIdsError(body) ??
    (body.answer != null && !["yes", "no"].includes(body.answer)
      ? "answer must be yes or no"
      : null),
  mark: (body) =>
    stepIdsError(body) ??
    (["done", "skipped"].includes(body.status) ? null : "status must be done or skipped"),
  config: configError,
  samples: samplesError,
  doc: stepIdsError,
};

/** Why the request has the wrong shape (a 400), or null when it's fine. */
function shapeError(body) {
  if (typeof body !== "object" || body === null || Array.isArray(body))
    return "the body must be a JSON object";
  if (!READ_ONLY.has(body.command) && !WRITING.has(body.command)) return "unknown setup command";
  return FIELD_CHECKS[body.command]?.(body) ?? null;
}

/** True for a command that only reads: it runs beside anything (requests.py build_call). */
const isReadOnly = ({ command, set: values, action }) =>
  READ_ONLY.has(command) ||
  (command === "config" && values == null) ||
  (command === "samples" && action === "count");

/** Writes `lines` as NDJSON, `lineMs` apart, then the exit record. */
async function stream(res, { lines, exit }, lineMs) {
  res.writeHead(200, { "content-type": "application/x-ndjson", "cache-control": "no-store" });
  for (const line of lines) {
    if (lineMs) await sleep(lineMs);
    res.write(`${JSON.stringify({ line })}\n`);
  }
  res.end(`${JSON.stringify({ exit })}\n`);
}

/** POST /api/setup/run with its parsed `body`, once the token and origin were checked. */
async function runSetup(res, body, { json, setupFail, setupFresh, setupDone, setupAll }) {
  const problem = shapeError(body);
  if (problem) return json(res, 400, { error: problem });
  const exclusive = !isReadOnly(body);
  if (exclusive && isWriting) return json(res, 409, { error: BUSY });
  const broken = setupFail && FAILING_COMMANDS.has(body.command);
  const result = broken
    ? { lines: BROKEN_PROGRESS, exit: EXIT_FAILED }
    : runCommand(body, { isFirstRun: setupFresh, isAllDone: setupDone, isAllPicked: setupAll });
  if (exclusive) isWriting = true;
  try {
    const isSlow = body.command === "apply" || body.command === "auto";
    await stream(res, result, isSlow ? STEP_LINE_MS : 0);
  } finally {
    if (exclusive) isWriting = false;
  }
}

/**
 * Answers the setup routes (`req`, its `res` and parsed `url`); false for any other path.
 *
 * @param {object} options {json, readJson} from mock-server.mjs, `setupFail`, `setupFresh`,
 *   `setupDone` and `setupAll`.
 * @returns {Promise<boolean>} True when the request was a setup route and got its answer.
 */
export async function handleSetup(req, res, url, options) {
  const { json, readJson } = options;
  if (req.method !== "POST") return false;
  if (url.pathname === TERMINAL_PATH) {
    const body = await readJson(req);
    // Nothing opens: the mock only checks the ids, like terminal.py, and says it worked.
    const problem = stepIdsError(body ?? {});
    if (problem) json(res, 400, { error: problem });
    else json(res, 200, { ok: true });
    return true;
  }
  if (url.pathname !== RUN_PATH) return false;
  await runSetup(res, await readJson(req), options);
  return true;
}
