// Mock console backend for developing the UI without tools/console/src.
// Speaks the contract in src/api: login key -> token, X-Console-Token on
// every request, /api/state, SSE with replay (plus a `tasks` event), /api/send
// and /api/action (run "in the server": running, then done or failed; its words
// are in actions/mock-actions.mjs, a board run's effect in actions/mock-board.mjs).
// The starting state is in mock-state.mjs, System's devices routes in
// mock-pages.mjs, its console checks (/api/health) in mock-health.mjs, model
// picks (/api/models) in mock-models.mjs, and Setup's and System's tools
// list's in setup/mock-setup.mjs.
// Any login key works except "bad" (the signed-out page); 401s and
// `--down-after` are in session/mock-session.mjs.
//
//   node dev/mock-server.mjs                 # api only, for `npm run dev`
//   node dev/mock-server.mjs --static dist   # also serve the build
//   node dev/mock-server.mjs --old-whiteboard  # daemon up but board.view null, like an older build
//   node dev/mock-server.mjs --whiteboard-off  # daemon down: no saves, no view, online false
//   node dev/mock-server.mjs --empty-board     # `items` view with 0 items: a load asks nothing
//   node dev/mock-server.mjs --night           # sleep mode's night view: calibration is off,
//                                               # and boards sent stay hidden under it
//   node dev/mock-server.mjs --many-saves      # 24 more saves: the list outgrows the view
//   node dev/mock-server.mjs --action-ms 20000  # slower button runs (a second board
//                                               # button meanwhile gets the busy refusal)
//   node dev/mock-server.mjs --setup-fail     # `setup list` and `setup status` fail
//   node dev/mock-server.mjs --setup-fresh    # first run: no picks, only the console built
//   node dev/mock-server.mjs --setup-done     # every pick finished: no Setup tab
//   node dev/mock-server.mjs --setup-all      # every tool picked: the wizard's longest strip
//   node dev/mock-server.mjs --claude closed  # none | closed | quiet | unknown (see mock-seed)
//   node dev/mock-server.mjs --away until     # until | default | asleep: start not Here
//   node dev/mock-server.mjs --health hooks   # port (default) | hooks | ok (see mock-health)
//   node dev/mock-server.mjs --empty-chat     # no seeded history: Chat and Voice open empty
//   node dev/mock-server.mjs --empty-lists    # no saved boards and no tasks: their empty states
//   node dev/mock-server.mjs --news-every 15  # a live unprompted reply or note every 15 s
//   node dev/mock-server.mjs --news-every 15 --long-news  # each reply taller than the view
//   node dev/mock-server.mjs --split-replay   # history arrives in two bursts 300 ms apart
//   node dev/mock-server.mjs --down-after 20  # stop answering 20 s after start, for 60 s
//   node dev/mock-server.mjs --many-tasks     # twelve active tasks, five need you: a crowded scope
//   node dev/mock-server.mjs --port 8795      # screen checks: 8790 is the real console's port
//   open http://127.0.0.1:8790/#k=dev
import http from "node:http";
import { randomUUID } from "node:crypto";
import { actionEcho, BUSY_WORDS, NOT_LINKED } from "./actions/mock-actions.mjs";
import { runBoardAction } from "./actions/mock-board.mjs";
import { healthBody } from "./mock-health.mjs";
import { applyPick } from "./mock-models.mjs";
import { handlePages, tasksPayload } from "./mock-pages.mjs";
import { REPLY, seedHistory, startNews, turnState } from "./mock-seed.mjs";
import { mockSaves, startState } from "./mock-state.mjs";
import { handleSetup } from "./setup/mock-setup.mjs";
import {
  BAD_LOGIN_KEY,
  downSwitch,
  NOT_SIGNED_IN,
  refuseSignedOut,
} from "./session/mock-session.mjs";
import { serveStatic } from "./static-files.mjs";

const HOST = "127.0.0.1";
const DEFAULT_PORT = 8790;
const TOKEN_HEADER = "x-console-token";
const MAX_BODY_BYTES = 64 * 1024;
const REPLAY_LIMIT = 200;
const HEARTBEAT_MS = 5_000;
const SPLIT_REPLAY_MS = 300;

const args = Object.fromEntries(
  process.argv
    .slice(2)
    .map((arg, i, all) => (arg.startsWith("--") ? [arg.slice(2), all[i + 1] ?? true] : [])),
);
const port = Number(args.port ?? DEFAULT_PORT);
const staticRoot = typeof args.static === "string" ? args.static : null;
const oldWhiteboard = Boolean(args["old-whiteboard"]);
const whiteboardOff = Boolean(args["whiteboard-off"]);
const emptyBoard = Boolean(args["empty-board"]);
const night = Boolean(args.night);
// `--empty-lists`: no saved boards and no tasks (their empty states).
const emptyLists = Boolean(args["empty-lists"]);
const saves = emptyLists ? [] : mockSaves(Boolean(args["many-saves"]));
const setupFail = Boolean(args["setup-fail"]);
const setupFresh = Boolean(args["setup-fresh"]);
const setupDone = Boolean(args["setup-done"]);
const setupAll = Boolean(args["setup-all"]);
// How long the fake server takes to run a button.
const DEFAULT_ACTION_MS = 3000;
const actionMs = Number(args["action-ms"] ?? DEFAULT_ACTION_MS);

const now = () => new Date().toISOString();

const state = startState({
  claude: args.claude,
  away: args.away,
  whiteboardOff,
  oldWhiteboard,
  emptyBoard,
  night,
  saves,
});

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
  // "fail" in the text simulates Claude's inbox rejecting the message.
  if (/fail/i.test(text)) {
    setTimeout(() => emitDelivery(id, "failed", NOT_LINKED), 300);
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
    if (state.voice.running) return { error: "Voice is already running" };
    state.voice = { running: true, phase: "listening", startedBy: "console" };
    emit("voice", { id: newId("v"), kind: "note", at: now(), text: "Voice started" });
    return { result: "Voice is running." };
  }
  if (action === "voice.stop") {
    state.voice = { running: false, phase: "off", startedBy: null };
    return { result: "Voice stopped." };
  }
  const { board, result } = runBoardAction(state.board, { action, name, saves, oldWhiteboard });
  state.board = board;
  return { result };
}

function handleAction(res, action, actionArgs) {
  const name = actionArgs?.name;
  const echo = actionEcho(action, name);
  if (!echo) return json(res, 400, { error: "unknown action" });
  if (action === "board.load" && !saves.some((save) => save.name === name)) {
    return json(res, 400, { error: "board.load needs the name of a current saved board" });
  }
  const lock = action.split(".")[0];
  if (busyLocks.has(lock)) return json(res, 409, { error: BUSY_WORDS[lock] });
  busyLocks.add(lock);
  const id = newId("m");
  emit("message", { id, role: "you", kind: "action", at: now(), text: echo });
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
  res.write(
    `event: tasks\ndata: ${JSON.stringify(tasksPayload(Boolean(args["many-tasks"]), emptyLists))}\n\n`,
  );
  const write = ({ event, data }) =>
    res.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  // `--split-replay`: the history's second half lands a beat later, as the real
  // server's one-write-per-event replay can reach the page in several chunks.
  const cut = args["split-replay"] ? Math.ceil(replay.length / 2) : replay.length;
  const rest = replay.slice(cut);
  replay.slice(0, cut).forEach(write);
  if (rest.length) setTimeout(() => rest.forEach(write), SPLIT_REPLAY_MS);
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
      return refuseSignedOut(json, res, BAD_LOGIN_KEY);
    const token = randomUUID();
    tokens.add(token);
    return json(res, 200, { token });
  }
  if (!tokens.has(req.headers[TOKEN_HEADER])) return refuseSignedOut(json, res, NOT_SIGNED_IN);
  if (url.pathname === "/api/state") return json(res, 200, state);
  if (url.pathname === "/api/health")
    return json(res, 200, healthBody({ variant: args.health, claude: args.claude, whiteboardOff }));
  if (url.pathname === "/api/events") return handleEvents(req, res);
  if (await handlePages(req, res, url, { json, readJson, state, emit })) return;
  const setupOptions = { json, readJson, setupFail, setupFresh, setupDone, setupAll };
  if (await handleSetup(req, res, url, setupOptions)) return;
  if (url.pathname === "/api/send" && req.method === "POST")
    return handleSend(res, (await readJson(req)).text);
  if (url.pathname === "/api/models" && req.method === "POST") {
    const refused = applyPick(state.models, await readJson(req));
    if (refused) return json(res, 400, { error: refused });
    emit("state", state);
    return json(res, 200, { ok: true });
  }
  if (url.pathname === "/api/action" && req.method === "POST") {
    const body = await readJson(req);
    return handleAction(res, body.action, body.args);
  }
  json(res, 404, { error: "no such route" });
}

if (!args["empty-chat"]) seedHistory(emit, newId);
if (args["news-every"])
  startNews(emit, newId, Number(args["news-every"]), { long: Boolean(args["long-news"]), setBusy });
// A down mock drops every request and open stream, like a stopped server.
const outage = downSwitch(Number(args["down-after"]), () => {
  for (const res of clients) res.destroy();
});
http
  .createServer(async (req, res) => {
    if (outage.isDown()) return req.socket.destroy();
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
