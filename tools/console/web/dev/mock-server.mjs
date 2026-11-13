// Mock console backend for developing the UI without tools/console/src.
// Speaks the contract in src/api: login key -> token, X-Console-Token on
// every request, /api/state, SSE with replay (plus a `tasks` event), /api/send
// and /api/action (run "in the server": running, then done or failed); the Devices page's routes are in
// mock-pages.mjs. Any login key works except "bad".
//
//   node dev/mock-server.mjs                 # api only, for `npm run dev`
//   node dev/mock-server.mjs --static dist   # also serve the build
//   node dev/mock-server.mjs --old-whiteboard  # daemon up but board.view null, like an older build
//   node dev/mock-server.mjs --whiteboard-off  # daemon down: no saves, no view, online false
//   node dev/mock-server.mjs --action-ms 20000  # slower button runs
//   open http://127.0.0.1:8790/#k=dev
import http from "node:http";
import { randomUUID } from "node:crypto";
import { handlePages, TASKS } from "./mock-pages.mjs";
import { REPLY, seedHistory } from "./mock-seed.mjs";
import { serveStatic } from "./static-files.mjs";

const HOST = "127.0.0.1";
const DEFAULT_PORT = 8790;
const TOKEN_HEADER = "x-console-token";
const MAX_BODY_BYTES = 64 * 1024;
const REPLAY_LIMIT = 200;
const HEARTBEAT_MS = 5_000;
const MS = { minute: 60_000, hour: 3_600_000, day: 86_400_000 };

const args = Object.fromEntries(
  process.argv
    .slice(2)
    .map((arg, i, all) => (arg.startsWith("--") ? [arg.slice(2), all[i + 1] ?? true] : [])),
);
const port = Number(args.port ?? DEFAULT_PORT);
const staticRoot = typeof args.static === "string" ? args.static : null;
const oldWhiteboard = Boolean(args["old-whiteboard"]);
const whiteboardOff = Boolean(args["whiteboard-off"]);
// How long the fake server takes to run a button.
const DEFAULT_ACTION_MS = 3000;
const actionMs = Number(args["action-ms"] ?? DEFAULT_ACTION_MS);

const ago = (ms) => new Date(Date.now() - ms).toISOString();
const now = () => new Date().toISOString();

// The whiteboard's saves. The real console reads them from the daemon, so an
// off whiteboard lists none; its view is `items` or `todo`, never a save name.
const SAVES = [
  {
    name: "lecture",
    updatedAt: ago(2 * MS.hour),
    description: "Week 7 lecture notes: queueing models and the M/M/1 example.",
  },
  {
    name: "agent-task-grid",
    updatedAt: ago(MS.day),
    description: "Grid of the agents' tasks and their status, one cell each.",
    refresher: "tasks",
  },
  { name: "hist-205-notes", updatedAt: ago(3 * MS.day), description: null },
  { name: "club-demo", updatedAt: null, description: "Demo flow for the club meeting." },
];

const state = {
  orchestrator: { claimed: true, label: "main", turn: turnState(false) },
  voice: { running: true, phase: "listening", startedBy: "console" },
  board: {
    saves: whiteboardOff ? [] : SAVES,
    view: whiteboardOff || oldWhiteboard ? null : "items",
    online: !whiteboardOff,
  },
  // The model strip's block (signal_console.models); picks aren't mocked.
  models: {
    orchestrator: {
      now: { model: "claude-opus-5-5", effort: "medium" },
      next: { model: null, effort: "high" },
    },
    voice: { model: null, effort: null },
    choices: {
      orchestrator: {
        model: [
          null,
          "default",
          "best",
          "fable",
          "opus",
          "sonnet",
          "haiku",
          "opus[1m]",
          "sonnet[1m]",
          "opusplan",
        ],
        effort: [null, "low", "medium", "high", "xhigh"],
      },
      voice: {
        model: [
          "default",
          "best",
          "fable",
          "opus",
          "sonnet",
          "haiku",
          "opus[1m]",
          "sonnet[1m]",
          "opusplan",
        ],
        effort: ["low", "medium", "high", "xhigh"],
      },
    },
  },
};

const tokens = new Set();
const replay = [];
const clients = new Set();
let nextId = 1;
const newId = (prefix) => `${prefix}-${nextId++}`;

function emit(event, data) {
  replay.push({ event, data });
  if (replay.length > REPLAY_LIMIT) replay.shift();
  for (const res of clients) res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
}

function emitDelivery(messageId, status, error) {
  emit("delivery", { id: newId("d"), messageId, status, ...(error ? { error } : {}) });
}

// The real server derives this from the turn hooks; here a reply ends the turn.
function turnState(working) {
  const at = Date.now();
  return {
    state: working ? "working" : "idle",
    startedAt: working ? at : null,
    lastActivityAt: at,
    agents: 0,
    agentsUnsure: false,
  };
}

function setBusy(busy) {
  state.orchestrator.turn = turnState(busy);
  emit("state", state);
}

function readJson(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => {
      body += chunk;
      if (body.length > MAX_BODY_BYTES)
        reject(Object.assign(new Error("body too large"), { status: 413 }));
    });
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch {
        reject(Object.assign(new Error("bad json"), { status: 400 }));
      }
    });
  });
}

const json = (res, status, body) => {
  res.writeHead(status, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
};

function handleSend(res, text) {
  if (typeof text !== "string" || !text.trim()) return json(res, 400, { error: "text required" });
  const id = newId("m");
  emit("message", { id, role: "you", kind: "chat", at: now(), text });
  json(res, 202, { id });
  // "fail" in the text simulates the orchestrator rejecting the message.
  if (/fail/i.test(text)) {
    setTimeout(() => emitDelivery(id, "failed", "no orchestrator claimed"), 300);
    return;
  }
  setTimeout(() => emitDelivery(id, "sent"), 300);
  setTimeout(() => setBusy(true), 400);
  setTimeout(() => {
    emit("message", {
      id: newId("m"),
      role: "claude",
      kind: "chat",
      at: now(),
      text: `You said: ${text}\n\n${REPLY}`,
    });
    setBusy(false);
  }, 4000);
}

// Like the real server: one action per lock (voice, board) at a time, 409 for a second.
const busyLocks = new Set();

// What the fake run changes and says; null result means it fails with `error`.
function applyAction(action, name) {
  if (action === "voice.start") {
    if (state.voice.running) return { error: "a voice hub is already running" };
    state.voice = { running: true, phase: "listening", startedBy: "console" };
    emit("voice", { id: newId("v"), kind: "note", at: now(), text: "voice hub started" });
    return { result: "Voice hub starting (pid 4242)." };
  }
  if (action === "voice.stop") {
    state.voice = { running: false, phase: "off", startedBy: null };
    return { result: "Voice hub stopped." };
  }
  // A board command starts the whiteboard (the whiteboard CLI does) if it was off.
  state.board = { ...state.board, online: true, saves: SAVES };
  // An older build keeps reporting no view, whatever is loaded.
  if (!oldWhiteboard) state.board.view = ({ "board.todo": "todo", "board.idle": "idle" })[action] ?? "items";
  if (action === "board.calibrate")
    return { result: "Calibration finished. calibrated: reprojection error 0.41 px" };
  return { result: `Done: ${name ? `'${name}'` : action}.` };
}

function handleAction(res, action, actionArgs) {
  const name = actionArgs?.name;
  const echoes = {
    "voice.start": "Start the voice hub",
    "voice.stop": "Stop the voice hub",
    "board.load": `Load the board "${name}"`,
    "board.todo": "Show the to-do list on the board",
    "board.idle": "Show the idle board on the board",
    "board.realign": "Realign the board",
    "board.calibrate": "Fully calibrate the board",
    "board.update": `Update the board "${name ?? "to-do list"}"`,
  };
  if (!echoes[action]) return json(res, 400, { error: "unknown action" });
  if (action === "board.load" && !SAVES.some((save) => save.name === name)) {
    return json(res, 400, { error: "board.load needs the name of a current whiteboard save" });
  }
  const lock = action.split(".")[0];
  if (busyLocks.has(lock)) return json(res, 409, { error: "still busy with the last button" });
  busyLocks.add(lock);
  const id = newId("m");
  emit("message", { id, role: "you", kind: "action", at: now(), text: echoes[action] });
  emitDelivery(id, "running");
  json(res, 202, { id });
  setTimeout(() => {
    busyLocks.delete(lock);
    const { result, error } = applyAction(action, name);
    emit("state", state);
    if (error) emitDelivery(id, "failed", error);
    else emit("delivery", { id: newId("d"), messageId: id, status: "done", result });
  }, actionMs);
}

function handleEvents(req, res) {
  res.writeHead(200, {
    "content-type": "text/event-stream",
    "cache-control": "no-cache",
    connection: "keep-alive",
  });
  res.write(`event: state\ndata: ${JSON.stringify(state)}\n\n`);
  res.write(`event: tasks\ndata: ${JSON.stringify(TASKS)}\n\n`);
  for (const { event, data } of replay)
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  clients.add(res);
  const heartbeat = setInterval(() => res.write(": keepalive\n\n"), HEARTBEAT_MS);
  req.on("close", () => {
    clients.delete(res);
    clearInterval(heartbeat);
  });
}

async function handleApi(req, res, url) {
  if (req.method === "POST") {
    const origin = req.headers.origin;
    if (origin && new URL(origin).host !== req.headers.host)
      return json(res, 403, { error: "bad origin" });
  }
  if (url.pathname === "/api/login" && req.method === "POST") {
    const { key } = await readJson(req);
    // Any key logs in except "bad", which shows the 401 page on purpose.
    if (typeof key !== "string" || !key || key === "bad")
      return json(res, 401, { error: "bad login key" });
    const token = randomUUID();
    tokens.add(token);
    return json(res, 200, { token });
  }
  if (!tokens.has(req.headers[TOKEN_HEADER])) return json(res, 401, { error: "not logged in" });
  if (url.pathname === "/api/state") return json(res, 200, state);
  if (url.pathname === "/api/events") return handleEvents(req, res);
  if (await handlePages(req, res, url, { json, readJson })) return;
  if (url.pathname === "/api/send" && req.method === "POST")
    return handleSend(res, (await readJson(req)).text);
  if (url.pathname === "/api/action" && req.method === "POST") {
    const body = await readJson(req);
    return handleAction(res, body.action, body.args);
  }
  json(res, 404, { error: "no such route" });
}

seedHistory(emit, newId);
http
  .createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    try {
      if (url.pathname.startsWith("/api/")) await handleApi(req, res, url);
      else if (staticRoot) await serveStatic(res, staticRoot, url.pathname);
      else json(res, 404, { error: "api only; pass --static dist to serve the build" });
    } catch (error) {
      json(res, error.status ?? 500, { error: error.message });
    }
  })
  .listen(port, HOST, () => console.log(`mock console backend on http://${HOST}:${port}/#k=dev`));
