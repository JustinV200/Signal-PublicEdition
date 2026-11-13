// Diagram renderers for the board page: mermaid (dark theme, bright lines, no fills)
// and rough.js hand-drawn shapes. Fills stay black because projected fills would
// wash out the owner's ink.

import { fitSvgToBox } from "./dom.js";

const SVG_NS = "http://www.w3.org/2000/svg";
const BLACK = "#000000";
const ROUGHNESS = 1.2;
const ARROW_HEAD_SPREAD = Math.PI / 7;
const MIN_ARROW_HEAD_PX = 14;
// Shapes whose strokes get the item's stroke width in a mermaid diagram.
const MERMAID_STROKED = "path, rect, circle, ellipse, polygon, line, polyline";

// mermaid.initialize is global, so renders run one at a time, each with its own theme.
let mermaidQueue = Promise.resolve();
let mermaidCount = 0;

export function renderMermaid(box, item) {
  const job = mermaidQueue.then(() => drawMermaid(box, item));
  mermaidQueue = job.catch(() => {});
  return job;
}

async function drawMermaid(box, item) {
  const { color, stroke_width: strokeWidth } = item.style;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    // Only the "base" theme honours themeVariables; mermaidTheme() makes it dark.
    theme: "base",
    look: "classic",
    fontFamily: "Segoe UI, sans-serif",
    themeVariables: mermaidTheme(color),
  });
  const id = `mermaid-${++mermaidCount}`;
  try {
    const { svg } = await mermaid.render(id, item.content);
    box.innerHTML = svg;
  } finally {
    // On a syntax error mermaid can leave its scratch element in <body>.
    document.getElementById(`d${id}`)?.remove();
  }
  const svgEl = box.querySelector("svg");
  fitSvgToBox(svgEl);
  for (const shape of svgEl.querySelectorAll(MERMAID_STROKED)) {
    // Arrowhead markers keep their own size.
    if (!shape.closest("marker")) shape.style.strokeWidth = `${strokeWidth}px`;
  }
}

function mermaidTheme(color) {
  return {
    darkMode: true,
    background: BLACK,
    mainBkg: BLACK,
    primaryColor: BLACK,
    secondaryColor: BLACK,
    tertiaryColor: BLACK,
    clusterBkg: BLACK,
    edgeLabelBackground: BLACK,
    primaryTextColor: color,
    secondaryTextColor: color,
    textColor: color,
    titleColor: color,
    primaryBorderColor: color,
    nodeBorder: color,
    clusterBorder: color,
    lineColor: color,
  };
}

// Content is a JSON list of shapes in item-local pixels (see display/scene/content.py).
export function renderRough(box, item) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${item.w} ${item.h}`);
  const canvas = rough.svg(svg);
  for (const shape of JSON.parse(item.content)) {
    const options = {
      stroke: shape.color ?? item.style.color,
      strokeWidth: shape.stroke_width ?? item.style.stroke_width,
      roughness: item.style.rough ? ROUGHNESS : 0,
      bowing: item.style.rough ? 1 : 0,
    };
    for (const node of drawShape(canvas, shape, options)) svg.appendChild(node);
  }
  box.append(svg);
}

function drawShape(canvas, shape, options) {
  switch (shape.shape) {
    case "rect":
      return [canvas.rectangle(shape.x, shape.y, shape.w, shape.h, options)];
    case "ellipse":
      return [canvas.ellipse(shape.x + shape.w / 2, shape.y + shape.h / 2, shape.w, shape.h, options)];
    case "line":
      return [canvas.line(shape.x1, shape.y1, shape.x2, shape.y2, options)];
    case "arrow":
      return drawArrow(canvas, shape, options);
    case "path":
      return [canvas.path(shape.d, options)];
    default:
      throw new Error(`unknown rough shape ${shape.shape}`);
  }
}

function drawArrow(canvas, { x1, y1, x2, y2 }, options) {
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = Math.max(MIN_ARROW_HEAD_PX, options.strokeWidth * 5);
  const barb = (side) => [
    x2 - head * Math.cos(angle + side * ARROW_HEAD_SPREAD),
    y2 - head * Math.sin(angle + side * ARROW_HEAD_SPREAD),
  ];
  return [
    canvas.line(x1, y1, x2, y2, options),
    canvas.line(x2, y2, ...barb(1), options),
    canvas.line(x2, y2, ...barb(-1), options),
  ];
}
