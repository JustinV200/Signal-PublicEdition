// The mock setup CLI's data: a small registry of tools mid-setup, so every
// wizard page, step kind and step and tool status (done, skipped, failed, to
// do; done, started, failed, skipped, not set up) shows, plus the intro, the tour
// and the missing programs; or, for --setup-fresh, the same registry as a first
// run leaves it. Each finished tool's check is in mock-setup-checks.mjs, and
// the entry builders in mock-setup-entries.mjs. Neutral on purpose: the tools
// and wording follow tools/setup's registry, nothing names a real person.
// Used by mock-setup-cli.mjs, which keeps the live copy.
import { asFirstRun, install, step, tool } from "./mock-setup-entries.mjs";

// The intro paragraph `setup intro` prints (tools/setup data/intro.txt), shortened.
export const INTRO =
  "Signal is a personal assistant system for Claude Code that runs on your own PC. It gives Claude local tools: a gated web browser, Gmail, a catch-up brief for when you're away, background Claude sessions, a task console and more. You pick only the tools you want, and setup installs, signs in and checks each one for you.";

// `setup tour --json`: GUIDE.md's sections, a few of them, with the markdown it uses.
export const TOUR = [
  {
    heading: "The big picture",
    body: "You talk to one main Claude Code session. Following [AGENTS.md](AGENTS.md), it plans the work and hands each task to a helper agent. A fresh reviewer checks every result before anything is committed.",
  },
  {
    heading: "How tools plug in",
    body: "- **MCP servers** (browser, mail, brief, sessions) give Claude tools it calls by name. Setup lists them in `.mcp.json`.\n- **Hooks** run small scripts on Claude Code events: the brief reads new prompts and the console follows turns.\n- **Command-line tools** work without a session open.",
  },
  {
    heading: "Task console",
    body: "A terminal-style window onto your main session, with a Tasks page showing what each agent is doing. Open it with `uv run --project tools/console --frozen --no-sync console open`.",
  },
];

// `setup prereqs`: the programs this PC lacks, and which tools use each.
export const MISSING_PREREQS = [
  {
    name: "Docker Desktop",
    get_it: "https://www.docker.com/products/docker-desktop/",
    usedBy: ["browser"],
  },
];

const CONSOLE_CLI = "uv run --project tools/console --frozen --no-sync console";
const CONSOLE_TASKS = `${CONSOLE_CLI} tasks:*`;
// The registry's console hooks: the turn hook on four events, the session hook on two.
const CONSOLE_HOOKS = [
  ...["UserPromptSubmit", "Stop", "StopFailure", "Notification"].map((event) => ({
    event,
    module: "signal_console.hooks.turn",
  })),
  ...["SessionStart", "PostModelSwitch"].map((event) => ({
    event,
    module: "signal_console.hooks.session",
  })),
];

/**
 * A fresh copy of the registry, so the mock's clicks never change the module's data.
 *
 * @param {{isFirstRun?: boolean}} options isFirstRun: a fresh checkout (--setup-fresh)
 *   instead of the usual mid-setup progress.
 * @returns {object[]} The tools with their progress.
 */
export function freshTools({ isFirstRun = false } = {}) {
  const tools = [
    tool(
      "brief",
      "Catch-up brief for when you're away",
      "Sessions log what you should hear about; 'brief me' gives a ranked catch-up.",
      {
        mcp: ["brief"],
        allow: ["mcp__brief"],
        hooks: [{ event: "UserPromptSubmit", module: "brief_tool.hooks.prompt" }],
      },
      [install("brief")],
    ),
    tool(
      "copytone",
      "Writing in your voice (copytone)",
      "Claude learns your voice from your own writing and drafts outbound text in it.",
      { platform: "Windows + Linux (untested)", prereqs: [] },
      [
        step(
          "samples",
          "Add writing samples (files, pasted text, or your own sent mail)",
          "samples",
          {
            optional: true,
          },
        ),
        step("voice-test", "Check the voice", "manual", {
          optional: true,
          text: 'In Claude Code, say: "test my copytone voice". Claude rewrites a short paragraph in your voice and asks if it sounds right.',
          doc: ".claude/skills/copytone/SKILL.md",
        }),
      ],
    ),
    tool(
      "console",
      "Task console",
      "A terminal-style window onto your main Claude Code session, with a Tasks page.",
      {
        prereqs: ["uv", "node", "edge"],
        allow: [`Bash(${CONSOLE_TASKS})`, `PowerShell(${CONSOLE_TASKS})`],
        hooks: CONSOLE_HOOKS,
      },
      [
        install("console"),
        step("web-deps", "Install the web front end's packages", "run", {
          command: "npm ci --prefix tools/console/web",
          status: "done",
        }),
        step("web-build", "Build the web front end", "run", {
          command: "npm run build --prefix tools/console/web",
          status: "done",
        }),
        // The logon task and Start-menu shortcut; {port} is the port step's answer.
        step(
          "logon",
          "Start the console server at every login, and add it to the Start menu",
          "run",
          {
            optional: true,
            command: `powershell -NoProfile -ExecutionPolicy Bypass -File tools/console/register.ps1 -Port {port}`,
            status: "done",
          },
        ),
        step("claim", "Claim your main session", "manual", {
          optional: true,
          text: `Paste this into Claude Code (your main session, not a plain terminal):\n  Run this with your Bash tool: ${CONSOLE_CLI} claim\nThe setup skill does this for you. Then open the console with:\n  ${CONSOLE_CLI} open`,
          doc: "tools/console/README.md",
          status: "done",
        }),
      ],
    ),
    tool(
      "audiohub",
      "Voice and music control",
      "Speaks agents' notifications aloud in order, and plays, pauses and searches music.",
      // Set up and Active, though its hub isn't running: its check passes with a fix.
      { prereqs: ["uv", "claude"], mcp: ["audiohub"], allow: ["mcp__audiohub"] },
      [
        install("audiohub"),
        step("config", "Create tools/audiohub/audiohub.toml and choose its settings", "settings", {
          optional: true,
          status: "skipped",
        }),
      ],
    ),
    tool(
      "browser",
      "Gated web browser",
      "Lets Claude drive a dedicated Edge profile on sites you allow.",
      { prereqs: ["uv", "edge"], mcp: ["browser"] },
      [
        install("browser"),
        step("config", "Create tools/browser/browser.toml and choose its settings", "settings"),
        step("auto-approve", "Auto-approve browser actions in Claude Code?", "confirm", {
          optional: true,
        }),
        step("docker", "Container browser (needs Docker Desktop)", "run", {
          optional: true,
          default: false,
          command: "docker build -t signal-browser:latest tools/browser",
        }),
        step("docker-config", "Copy the container browser's config", "copy", {
          optional: true,
          default: false,
          status: "skipped",
        }),
      ],
    ),
    tool(
      "vault",
      "Password vault",
      "Lets the browser log in to your accounts without any password reaching the model.",
      {},
      // Its install isn't done yet, so its Run the automatic steps button shows; its
      // init failed in a terminal, so the tool reads failed.
      [
        install("vault", ""),
        step("init", "Create the vault (Windows Hello asks three times)", "run", {
          terminal: true,
          command: "uv run --project tools/vault --frozen --no-sync vault init",
          status: "failed",
        }),
      ],
    ),
    tool(
      "mail",
      "Gmail",
      "Search, read and draft mail in your Gmail accounts.",
      {
        mcp: ["mail"],
        allow: ["mcp__mail__mail_search", "mcp__mail__mail_read", "mcp__mail__mail_draft"],
      },
      // Set up, but its check fails (mock-setup-checks.mjs): System's Fix opens this page.
      [
        install("mail"),
        step("google-project", "Create the Google Cloud project and its sign-in client", "manual", {
          text: "Follow steps 1 to 3 of tools/mail/SETUP.md.",
          doc: "tools/mail/SETUP.md",
          status: "done",
        }),
        step("email", "Your Gmail address", "email", { status: "done" }),
        step("signin", "Sign in (opens your browser)", "run", {
          opens_browser: true,
          command:
            "uv run --project tools/mail --frozen --no-sync mail add personal --email {email}",
          status: "done",
        }),
        step("more-accounts", "More accounts", "manual", {
          optional: true,
          default: false,
          doc: "tools/mail/SETUP.md",
        }),
      ],
    ),
    tool(
      "calendar",
      "Google Calendar",
      "Reads your calendars for the agenda, and lets Claude add events and change them.",
      { needs: ["mail"], skipped: true },
      [install("calendar", "")],
    ),
    tool(
      "sessions",
      "Background Claude sessions",
      "Starts and drives headless Claude Code sessions in your other git repos.",
      // Done but not in Claude Code's config yet: reads "not added", never Active.
      {
        mcp: ["sessions"],
        // The registry's four read-only rules, not the whole server.
        allow: ["list_sessions", "list_managed_sessions", "list_repos", "session_status"].map(
          (name) => `mcp__sessions__${name}`,
        ),
        wired: false,
      },
      [
        install("sessions"),
        step("repo-roots", "Folders that hold your git repos (';'-separated)", "env", {
          optional: true,
          default: false,
        }),
      ],
    ),
    tool(
      "whiteboard",
      "Projector whiteboard",
      "A projector and webcam turn a physical whiteboard into one Claude can see and draw on.",
      { prereqs: ["uv", "edge"], touched: false },
      [install("whiteboard", ""), step("calibrate", "Align the projector to the board", "manual")],
    ),
    tool(
      "sleepmode",
      "Sleep mode",
      "Darkens every screen and turns RGB lights off while the PC and agents keep running.",
      { skipped: true },
      [install("sleepmode", "")],
    ),
  ];
  return isFirstRun ? tools.map(asFirstRun) : tools;
}
