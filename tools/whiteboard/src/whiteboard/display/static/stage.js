// Stage layout and display modes for the board page.
// #screen is the projector (projector pixels) scaled to fit the window. #stage is the
// logical board inside it, warped onto the board quad with a CSS matrix3d computed by
// the daemon (display/scene/fit.py). Pattern markers and the fit outline sit in #screen,
// unwarped, because they're given in projector pixels.

import { place } from "./dom.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const screenEl = document.getElementById("screen");
const stageEl = document.getElementById("stage");
const highlightsEl = document.getElementById("highlights");
const outlineEl = document.getElementById("fit-outline");
const polygonEl = document.getElementById("fit-polygon");
const patternEl = document.getElementById("pattern");

let projector = { width: 1280, height: 720 };

// Apply the stage geometry from a scene message: {width, height, matrix3d, quad, projector}.
export function applyStage(stage) {
  projector = stage.projector;
  setSize(screenEl, projector.width, projector.height);
  setSize(stageEl, stage.width, stage.height);
  const layers = ["items", "todo", "idle", "night"].map((id) => document.getElementById(id));
  for (const layer of [...layers, highlightsEl]) {
    setSize(layer, stage.width, stage.height);
  }
  stageEl.style.transform = stage.matrix3d ? `matrix3d(${stage.matrix3d.join(",")})` : "none";
  drawOutline(stage.quad);
  fitScreenToWindow();
}

// Switch display mode (normal, blank, pattern, fit). Markers are {url, x, y, w, h}.
export function setMode(mode, markers) {
  patternEl.replaceChildren(...markers.map(markerImage));
  document.body.dataset.mode = mode;
}

// Show the projected items ("items"), the TODO view ("todo"), the idle view ("idle") or
// the night view ("night"); board.css hides the others.
export function setView(view) {
  document.body.dataset.view = view;
}

// Flash a bright box at {x, y, w, h} (stage pixels) for `seconds`.
export function flashHighlight({ x, y, w, h, seconds }) {
  const box = document.createElement("div");
  box.className = "highlight";
  place(box, x, y, w, h);
  highlightsEl.append(box);
  setTimeout(() => box.remove(), seconds * 1000);
}

// Letterbox the projector-sized #screen into the window (1:1 on the projector itself).
function fitScreenToWindow() {
  const scale = Math.min(innerWidth / projector.width, innerHeight / projector.height);
  const left = (innerWidth - projector.width * scale) / 2;
  const top = (innerHeight - projector.height * scale) / 2;
  screenEl.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
}

// Outline the board quad, or the whole projector when there's no fit. The outline
// is inset by half its stroke so it stays fully visible at the projector's edges.
function drawOutline(quad) {
  const inset = 2;
  const { width, height } = projector;
  const corners = quad ?? [[inset, inset], [width - inset, inset],
    [width - inset, height - inset], [inset, height - inset]];
  setSize(outlineEl, width, height);
  outlineEl.setAttribute("viewBox", `0 0 ${width} ${height}`);
  polygonEl.setAttribute("points", corners.map((point) => point.join(",")).join(" "));
}

function markerImage({ url, x, y, w, h }) {
  const image = document.createElement("img");
  image.className = "pattern-marker";
  image.src = url;
  place(image, x, y, w, h);
  return image;
}

function setSize(element, width, height) {
  if (element.namespaceURI === SVG_NS) {
    element.setAttribute("width", width);
    element.setAttribute("height", height);
  }
  Object.assign(element.style, { width: `${width}px`, height: `${height}px` });
}

window.addEventListener("resize", fitScreenToWindow);
