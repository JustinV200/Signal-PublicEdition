// Board page entry point: connects to the daemon's /ws and dispatches its messages.
// Messages: {type:"scene", items, view, night, stage}, {type:"mode", mode, markers},
// {type:"todo", todo, newly_done}, {type:"idle", idle}, {type:"highlight", x,y,w,h,seconds}.
// `night` is {seed, sky, previous_view} while the view is "night" (sleep mode), else null.
// Render failures go back to the daemon as {type:"render_error"} so they show up in its log.

import { fitIdle, renderIdle } from "./idle/idle.js";
import { startNight } from "./night/night.js";
import { renderScene } from "./renderers.js";
import { applyStage, flashHighlight, setMode, setView } from "./stage.js";
import { renderTodo } from "./todo.js";

const RECONNECT_MS = 1000;
const nightEl = document.getElementById("night");
let socket = null;
// The running night sky, {key, handle}, or null outside the night view.
let night = null;

function connect() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage = (event) => handleMessage(JSON.parse(event.data));
  // The daemon restarts now and then; keep retrying until it's back.
  socket.onclose = () => setTimeout(connect, RECONNECT_MS);
}

function handleMessage(message) {
  if (message.type === "scene") {
    applyStage(message.stage);
    fitIdle(message.stage);
    setView(message.view);
    showNight(message.night);
    renderScene(message.items, reportRenderError);
  } else if (message.type === "mode") {
    setMode(message.mode, message.markers);
  } else if (message.type === "todo") {
    renderTodo(message.todo, message.newly_done);
  } else if (message.type === "idle") {
    renderIdle(message.idle);
  } else if (message.type === "highlight") {
    flashHighlight(message);
  }
}

// Start the sky for the scene's night settings, or stop it once the view isn't night:
// hiding the layer alone would keep its frame loop running all day. Only a new seed or
// sky restarts it, since every start rebuilds the sky; scene messages come often.
function showNight(settings) {
  const key = settings ? `${settings.seed}/${settings.sky}` : null;
  if (key === (night?.key ?? null)) return;
  night?.handle.stop();
  night = null;
  if (settings) night = { key, handle: startNight(nightEl, settings) };
}

function reportRenderError(itemId, error) {
  console.error(`item ${itemId} failed to render`, error);
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "render_error", id: itemId, error: String(error) }));
  }
}

connect();
