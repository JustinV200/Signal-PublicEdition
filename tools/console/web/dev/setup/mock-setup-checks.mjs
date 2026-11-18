// The mock `setup status --json` (tools/setup health.py): one row per tool,
// active or down from a finished tool's check, else not set up, each with the
// check's words, fix and command in the shape verify.py gives them. Mail's
// check fails with a fix and a command (`mail check`, an unreadable saved
// sign-in); Voice's passes but carries a fix, since the hub isn't running
// (`audiohub check` exits 0 then). Used by mock-setup-cli.mjs, which passes in
// its live tools and how it works out each one's status and wiring.

// What each finished tool's check says. A finished tool missing here passes
// with "installed", as a check without a summary line does in tools/setup.
const CHECKS = {
  // `console doctor --summary-json` prints a summary only on a fail row: "installed" on a pass.
  console: { passed: true, words: "installed" },
  // No summary line, and it ran past the timeout: verify.py's words and the registry's fix.
  brief: {
    passed: false,
    words: "timed out after 8 s",
    fix: "Set the brief up again with setup brief.",
  },
  sessions: { passed: true, words: "2 repos found; daemon not running (starts on first use)" },
  mail: {
    passed: false,
    words: "The saved sign-in for personal is unreadable.",
    fix: "Sign personal in again.",
    command: "uv run --project tools/mail --frozen --no-sync mail add personal",
  },
  audiohub: {
    passed: true,
    words: "Installed, but the voice hub isn't running",
    fix: "Start it with Start voice in the console.",
    command: "uv run --env-file .env --project tools/audiohub --frozen --no-sync audiohub run",
  },
};
const PLAIN_PASS = { passed: true, words: "installed" };

// health.py's words for a tool that isn't done, by its setup status (none when never
// picked, so the row reads "Not set up" once).
const NOT_DONE_WORDS = {
  skipped: "skipped",
  "": "",
  started: "setup started, not finished",
  failed: "a setup step failed",
};

/**
 * The health rows `setup status --json` prints.
 *
 * @param {object[]} tools The live mock registry.
 * @param {{toolStatus: Function, isWired: Function}} helpers The CLI's status and wiring rules.
 * @returns {object[]} One row per tool.
 */
export function healthRows(tools, { toolStatus, isWired }) {
  return tools.map((tool) => {
    const status = toolStatus(tool);
    const isDone = status === "done";
    const check = isDone ? (CHECKS[tool.id] ?? PLAIN_PASS) : { passed: false };
    return {
      id: tool.id,
      name: tool.name,
      platform: tool.platform,
      supported_here: true,
      setup_status: status || "not set up",
      state: isDone ? (check.passed ? "active" : "down") : "not_set_up",
      words: isDone ? check.words : NOT_DONE_WORDS[status],
      fix: check.fix ?? null,
      command: check.command ?? null,
      wired: isWired(tool),
    };
  });
}
