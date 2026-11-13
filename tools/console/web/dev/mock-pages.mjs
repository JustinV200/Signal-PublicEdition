// The mock backend's Tasks and Devices data: a fixed `tasks` event, GET
// /api/devices, POST /api/away (kept in memory) and a camera stream that
// answers like the whiteboard's 2-viewer cap. Used by mock-server.mjs.
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

const DEVICES = [
  { id: "projector", name: "Projector", state: "on", words: "Projecting your board" },
  {
    id: "webcam",
    name: "Webcam",
    state: "on",
    words: "Live, 1920x1080 via msmf, calibrated",
    canOpen: true,
  },
  { id: "hub", name: "Voice hub", state: "on", words: "Running, listening (started by console)" },
  { id: "glasses", name: "Glasses", state: "on", words: "In use by the voice hub" },
  { id: "browser", name: "Desktop browser", state: "off", words: "Not running" },
  { id: "docker", name: "Docker (docker browser)", state: "unknown", words: "Unknown" },
];

let away = { state: "here", endsAt: null, note: "" };

/** Answers the Tasks/Devices routes; returns false for any other path. */
export async function handlePages(req, res, url, { json, readJson }) {
  if (url.pathname === "/api/devices") {
    json(res, 200, { devices: DEVICES, away });
    return true;
  }
  if (url.pathname === "/api/away" && req.method === "POST") {
    const { on } = await readJson(req);
    away = on
      ? { state: "away", endsAt: later(3 * 24 * 60), note: "" }
      : { state: "here", endsAt: null, note: "" };
    json(res, 200, away);
    return true;
  }
  if (url.pathname === "/api/camera/stream") {
    // No camera in the mock: say so the way the real proxy does for a full camera.
    json(res, 429, { error: "The camera already has 2 viewers, the whiteboard's limit." });
    return true;
  }
  return false;
}
