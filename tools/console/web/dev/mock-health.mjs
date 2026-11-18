// The mock GET /api/health: the console's own checks in the order and shape
// signal_console.health sends them, `{rows: [{id, name, level, state, words,
// fix, command}]}`, never a socket name or token. `--health` picks the case:
//   port  (the default) another checkout's console holds the port (O11): its
//         own row names that checkout's path, with the fix in words only
//   hooks the turn and session hooks are missing (fail), so `state unknown`
//         names its cause and Models points at the Console row
//   ok    every check passes
// The claim and whiteboard rows follow `--claude` and `--whiteboard-off`.
// Used by mock-server.mjs.

const SETUP_COMMAND = String.raw`.\setup.cmd console`;
const HOOK_FIX = "Add the console's hooks with setup, then restart Claude Code.";
const CLAIM_FIX = "In your main Claude Code session, have Claude run this with its Bash tool.";
const CLAIM_COMMAND = "uv run --project tools/console --frozen --no-sync console claim";
// A made-up second checkout with a space in its path, like a real one could have.
const OTHER_CHECKOUT = String.raw`C:\Example Folder\Signal-other`;
const PORT = 8790;

const row = (id, name, level, state, words, fix = null, command = null) => ({
  id,
  name,
  level,
  state,
  words,
  fix,
  command,
});

function portRow(variant) {
  if (variant !== "port")
    return row("port", "Console port", "ok", "ours", `Port ${PORT} is this console's.`);
  const words = `Port ${PORT} is held by the console of another checkout, ${OTHER_CHECKOUT}.`;
  const fix = "Stop that program, or run `console open --port <a free port>`.";
  return row("port", "Console port", "attention", "taken", words, fix);
}

function hookRow(id, name, events, variant) {
  if (variant !== "hooks")
    return row(
      id,
      name,
      "ok",
      "installed",
      `Registered for all ${events.length} events (${events.join(", ")}).`,
    );
  const words = `Not registered for ${events.join(", ")}, so the console misses those events.`;
  return row(id, name, "fail", "missing", words, HOOK_FIX, SETUP_COMMAND);
}

function claimRow(claude) {
  if (claude === "none")
    return row(
      "claim",
      "Claude session",
      "attention",
      "none",
      "No Claude Code session is linked to the console yet.",
      CLAIM_FIX,
      CLAIM_COMMAND,
    );
  if (claude === "closed")
    return row(
      "claim",
      "Claude session",
      "attention",
      "closed",
      'The session "main" (3d ago) has closed, so messages can\'t reach Claude.',
      CLAIM_FIX,
      CLAIM_COMMAND,
    );
  return row(
    "claim",
    "Claude session",
    "ok",
    "linked",
    'Claude Code session "main" is open (3d ago).',
  );
}

function reportRow(variant) {
  if (variant !== "hooks")
    return row(
      "hook-report",
      "Last hook report",
      "ok",
      "received",
      "Claude's last reply came through the turn hook at 2026-11-17 11:58.",
    );
  const fix = "Link a Claude Code session to the console, then let Claude finish one turn.";
  return row(
    "hook-report",
    "Last hook report",
    "attention",
    "none yet",
    "No reply from Claude has come through the turn hook yet.",
    fix,
  );
}

function whiteboardRow(isOff) {
  if (!isOff)
    return row(
      "whiteboard",
      "Whiteboard",
      "ok",
      "running",
      "The whiteboard is running on port 8770.",
    );
  const words = "The whiteboard isn't running, so the Boards page and the camera are empty.";
  return row(
    "whiteboard",
    "Whiteboard",
    "attention",
    "off",
    words,
    "It starts by itself the next time Claude uses the whiteboard.",
  );
}

/**
 * The health rows for one case.
 *
 * @param {{variant?: string, claude?: string, whiteboardOff?: boolean}} options `--health`,
 *   `--claude` and `--whiteboard-off` from the command line.
 * @returns {{rows: object[]}} The GET /api/health body.
 */
export function healthBody({ variant = "port", claude, whiteboardOff = false }) {
  return {
    rows: [
      row(
        "server",
        "Console server",
        "ok",
        "running",
        `The console server is running on port ${PORT}.`,
      ),
      portRow(variant),
      row("web-build", "Console page", "ok", "built", "The console's page is built."),
      claimRow(claude),
      hookRow(
        "turn-hook",
        "Turn hook",
        ["UserPromptSubmit", "Stop", "StopFailure", "Notification"],
        variant,
      ),
      hookRow("session-hook", "Session hook", ["SessionStart", "PostModelSwitch"], variant),
      row(
        "hooks-twice",
        "Hooks fire once",
        "ok",
        "once",
        "No console hook is in both settings files.",
      ),
      reportRow(variant),
      row(
        "hook-errors",
        "Hook errors",
        "ok",
        "none recent",
        "No hook errors in the last 24 hours.",
      ),
      row("edge", "Microsoft Edge", "ok", "found", "Edge is installed for the console window."),
      whiteboardRow(whiteboardOff),
      row(
        "hub-log",
        "Voice log",
        "ok",
        "no errors",
        "No errors in Voice's log from the last 24 hours.",
      ),
    ],
  };
}
