// The mock backend's Tasks and Devices data: a fixed `tasks` event (a crowded
// one with `--many-tasks`, an empty one with `--empty-lists`), GET
// /api/devices, POST /api/away (kept in the live state's `away`, which goes
// out on the stream like the real server's) and a camera stream that answers
// like the whiteboard's 2-viewer cap. Used by mock-server.mjs and
// mock-state.mjs.
const MS_PER_MINUTE = 60_000;
const at = (minutesAgo) => new Date(Date.now() - minutesAgo * MS_PER_MINUTE).toISOString();
const later = (minutes) => new Date(Date.now() + minutes * MS_PER_MINUTE).toISOString();

const task = (id, name, pct, status, number, next, you = "") => ({
  id,
  name,
  pct,
  status,
  number,
  next,
  you,
  updatedAt: at(5),
});

export const TASKS = {
  updatedAt: at(2),
  active: [
    task("console-p2", "Console phase 2", 80, "review", 1, "fresh reviewer on the web diff"),
    task("brief-p2", "Brief phase 2", 60, "needs_you", 3, "live test", "say yes to the hook"),
    task("mcp", "MCP re-read audit", 20, "building", 2, "sessions server"),
  ],
  queued: [task("checker", "Checker v2", 0, "queued", 4, "")],
  done: [task("hub", "Hub stop fix", 100, "done", 5, "")],
  needsYou: 1,
  overallPct: 40,
  usage: {
    fiveHour: { usedPct: 42, resetsAt: later(130) },
    sevenDay: null,
    agents: 5,
    updatedAt: at(2),
  },
};

// `--many-tasks`: a crowded scope, five tasks waiting on the owner among twelve
// (the scope's readout lists three and folds the other two into `+2 more`; its
// radar counts all five in one `5 NEED YOU`).
const MANY_ACTIVE = [
  task("wake", "Wake word tuning", 100, "needs_you", 3, "ship it", "confirm the wake word"),
  task("rules", "Checker rules pass", 100, "needs_you", 3, "merge", "approve the rule list"),
  task("links", "Docs link sweep", 100, "needs_you", 3, "publish", "pick a docs host"),
  task("console-p2", "Console phase 2", 92, "review", 1, "fresh reviewer on the web diff"),
  task("scope", "Scope radar rework", 85, "review", 1, "screen check"),
  task("brief-p2", "Brief phase 2", 60, "needs_you", 3, "live test", "say yes to the hook"),
  task("mail", "Mail draft threading", 55, "building", 2, "reply headers"),
  task("board", "Board saves cleanup", 45, "building", 2, "dedupe names"),
  task("hub", "Voice hub restart path", 40, "building", 2, "watchdog"),
  task("keys", "Login key rotation", 30, "needs_you", 3, "pick a lifetime", "pick 7 or 30 days"),
  task("mcp", "MCP re-read audit", 20, "building", 2, "sessions server"),
  task("docs", "Setup guide pass", 5, "building", 2, "first draft"),
];

/**
 * The `tasks` event: TASKS, twelve active tasks with `many`, or none at all
 * with `empty` (`--empty-lists`: the Tasks page's empty state; usage stays).
 */
export function tasksPayload(many, empty = false) {
  if (empty) return { ...TASKS, active: [], queued: [], done: [], needsYou: 0, overallPct: 0 };
  return many ? { ...TASKS, active: MANY_ACTIVE, needsYou: 5 } : TASKS;
}

const DEVICES = [
  { id: "projector", name: "Projector", state: "on", words: "Projecting a drawing" },
  {
    id: "webcam",
    name: "Webcam",
    state: "on",
    words: "Live, 1920x1080 via msmf, calibrated",
    canOpen: true,
  },
  { id: "hub", name: "Voice", state: "on", words: "Running, listening (started by the console)" },
  { id: "browser", name: "Desktop browser", state: "off", words: "Not running" },
  {
    id: "docker",
    name: "Docker (docker browser)",
    state: "on",
    words: "Docker Desktop is running",
  },
];

const MINUTES_PER_DAY = 24 * 60;

/**
 * An away block like signal_console.away's. Away with no end given has a null
 * endsAt, as the real server hides the brief's 3-day default.
 *
 * @param {string | undefined} mode `--away`'s value: `until` (away until tomorrow),
 *   `default` (away, no end given), `asleep`, or anything else for here.
 */
export function awayBlock(mode) {
  if (mode === "until") return { state: "away", endsAt: later(MINUTES_PER_DAY), note: "" };
  if (mode === "default") return { state: "away", endsAt: null, note: "" };
  if (mode === "asleep") return { state: "asleep", endsAt: null, note: "" };
  return { state: "here", endsAt: null, note: "" };
}

/**
 * Answers the Tasks/Devices routes; returns false for any other path.
 *
 * @param {{json: Function, readJson: Function, state: object, emit: Function}} io The
 *   reply helpers, the live state (its `away` is changed here) and the stream's emit.
 */
export async function handlePages(req, res, url, { json, readJson, state, emit }) {
  if (url.pathname === "/api/devices") {
    json(res, 200, { devices: DEVICES, away: state.away });
    return true;
  }
  if (url.pathname === "/api/away" && req.method === "POST") {
    const { on, until } = await readJson(req);
    // Any typed end reads as tomorrow; the mock doesn't parse it.
    state.away = awayBlock(on ? (until ? "until" : "default") : "here");
    emit("state", state);
    json(res, 200, state.away);
    return true;
  }
  if (url.pathname === "/api/camera/stream") {
    // No camera in the mock: say so the way the real proxy does for a full camera.
    json(res, 429, { error: "The camera already has 2 viewers, the whiteboard's limit." });
    return true;
  }
  return false;
}
