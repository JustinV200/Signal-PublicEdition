// The mock's `setup plan` (tools/setup wiring.summary_lines): one plain line per
// finished tool saying what Claude may do without asking (wiring/consent.py),
// then one blank line, then the exact entries, which the Permissions page folds
// under Show exact entries. The words are copies of the registry's `consent`.
// Used by mock-setup-cli.mjs.

// The registry's `consent` for the mock tools that add rules or hooks.
const CONSENT = {
  audiohub:
    "Claude can speak to you and control your music (play, pause, skip, queue, volume, liked songs, search, what's playing) without asking each time.",
  brief:
    "Claude can log to the brief, read it, mark items handled and turn Away on or off without asking each time. A hook adds the brief and the away rules to your prompts, reads the session's transcript, and marks items seen once Claude has passed them on.",
  console:
    "Claude can update the Tasks page without asking each time. Hooks tell the console when each turn starts, ends (with Claude's last reply) or waits for you, and which model each session runs.",
  mail: "Claude can search, read and draft mail without asking each time. Sending still asks.",
  sessions:
    "Claude can list your sessions and repos and check on a session without asking. Starting or messaging a session still asks.",
};
// consent.py's words for a tool without its own (or with nothing to approve).
const UNWORDED = "adds entries Claude Code uses without asking each time; see the exact entries.";
const ASKS_EACH_TIME = "Claude can use its tools, but asks you each time.";
const ADDS_NOTHING = "adds nothing to Claude Code.";

/**
 * One tool's plain line, a simplified copy of consent.consent_line: the mock has
 * no unattended_claude steps or status line, so it leaves out those two cases.
 */
function consentLine(tool) {
  let words = ADDS_NOTHING;
  if (tool.allow.length || tool.hooks.length) words = CONSENT[tool.id] ?? UNWORDED;
  else if (tool.mcp.length) words = ASKS_EACH_TIME;
  return `${tool.name}: ${words}`;
}

/**
 * What `setup plan` prints for the finished tools.
 *
 * @param {object[]} done The mock tools whose status is done, in registry order.
 * @returns {string[]} The plain lines, a blank line, then the exact entries.
 */
export function planLines(done) {
  const allow = done.flatMap((tool) => tool.allow);
  const hooks = done
    .flatMap((tool) => tool.hooks.map((hook) => `${hook.event}: ${tool.id} (${hook.module})`))
    .sort();
  const kept = "Your own permission settings, mode included, stay as they are.";
  const plain = done.length
    ? [...done.map(consentLine), `Setup auto-approves nothing else. ${kept}`]
    : [`No tool is finished yet, so setup adds nothing. ${kept}`];
  return [
    ...plain,
    "",
    `Tools to wire: ${done.map((tool) => tool.id).join(", ") || "none"}`,
    `MCP servers (.mcp.json): ${done.flatMap((tool) => tool.mcp).join(", ") || "none"}`,
    "Auto-approved in Claude Code (.claude/settings.local.json):",
    ...(allow.length ? allow.map((rule) => `  ${rule}`) : ["  nothing"]),
    "Hooks (.claude/settings.local.json):",
    ...(hooks.length ? hooks.map((hook) => `  ${hook}`) : ["  none"]),
  ];
}
