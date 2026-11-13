// Aurora (effects/): a ribbon of soft crimson, magenta and violet strokes along one edge
// of the board, each swaying and breathing slowly. Drawn behind the stars.

import { fillSoftDisk } from "../../paint.js";
import { between, pick } from "../../random.js";
import { swell } from "../../timing.js";

const EDGES = 4; // top, right, bottom, left
const STROKES = [5, 7];
const HUES = [[1, 0.2, 0.35], [1, 0.25, 0.72], [0.6, 0.3, 1]]; // crimson, magenta, violet
const ALONG = [0.05, 0.95]; // where along the edge, as a fraction of its length
const WIDTH = [0.08, 0.14]; // of the edge's length
const DEPTH = [0.18, 0.3]; // how far into the board, of the other side's length
const ALPHA = [0.35, 0.5];
const SWAY = 0.03; // of the edge's length
const SWAY_S = [40, 70];
const BREATH_S = [30, 50];
const BREATH_DEPTH = 0.4;

export default {
  name: "aurora",
  family: "aurora",
  layer: "behind",
  build(next) {
    const strokes = [];
    const count = Math.round(between(next, ...STROKES));
    for (let i = 0; i < count; i++) {
      strokes.push({
        along: between(next, ...ALONG),
        width: between(next, ...WIDTH),
        depth: between(next, ...DEPTH),
        alpha: between(next, ...ALPHA),
        rgb: pick(next, HUES),
        sway: { period: between(next, ...SWAY_S), phase: next() * 2 * Math.PI },
        breath: { period: between(next, ...BREATH_S), phase: next() * 2 * Math.PI },
      });
    }
    return { edge: Math.floor(next() * EDGES), strokes };
  },
  draw(context, state, frame) {
    const { length, depth } = enterEdge(context, state.edge, frame);
    for (const stroke of state.strokes) {
      const sway = SWAY * Math.sin((2 * Math.PI * frame.t) / stroke.sway.period + stroke.sway.phase);
      const radiusX = (stroke.width * length) / 2;
      const radiusY = stroke.depth * depth;
      const breath = 1 - BREATH_DEPTH * swell(frame.t, stroke.breath);
      context.save();
      context.translate((stroke.along + sway) * length, 0);
      context.scale(1, radiusY / radiusX);
      fillSoftDisk(context, radiusX, stroke.rgb, stroke.alpha * breath);
      context.restore();
    }
  },
};

// Turn the context so x runs along the chosen edge and +y into the board; returns the
// edge's length and the board's depth beyond it.
function enterEdge(context, edge, frame) {
  const { width, height } = frame;
  if (edge === 1) {
    context.translate(width, 0);
    context.rotate(Math.PI / 2);
  } else if (edge === 2) {
    context.translate(width, height);
    context.rotate(Math.PI);
  } else if (edge === 3) {
    context.translate(0, height);
    context.rotate(-Math.PI / 2);
  }
  const sideways = edge % 2 === 1;
  return { length: sideways ? height : width, depth: sideways ? width : height };
}
