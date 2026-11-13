// Satellite (effects/): every few minutes a small steady point crosses the board in
// about a minute and a half, with a gentle glint half way across.

import { crossing, crossingPoint } from "../../geometry.js";
import { fillDot, fillHalo } from "../../paint.js";
import { between, childSeed } from "../../random.js";
import { envelope, eventAt } from "../../timing.js";

const PERIOD_S = [420, 600];
const CROSSING_S = 90;
const PATH = { heights: [0.1, 0.9], margin: 0.05 }; // enters and leaves just outside the frame
const COLOUR = [1, 0.9, 0.72]; // warm white
const RADIUS_PX = 1.6; // at 1080p
const ALPHA = 0.75;
const GLINT = { rise: 3, hold: 0, fall: 3 };
const GLINT_RADIUS = 7; // of the point's radius
const GLINT_ALPHA = 0.5;

export default {
  name: "satellite",
  family: "satellite",
  build(next) {
    return { schedule: { period: between(next, ...PERIOD_S), seed: childSeed(next) } };
  },
  draw(context, state, frame) {
    const event = eventAt(frame.t, state.schedule, CROSSING_S);
    if (!event) return;
    const path = crossing(event.next, PATH);
    const { x, y } = crossingPoint(path, event.local / CROSSING_S, frame);
    const radius = RADIUS_PX * frame.px;
    const glint = envelope(event.local, CROSSING_S / 2 - GLINT.rise, GLINT);
    if (glint > 0) fillHalo(context, x, y, radius * GLINT_RADIUS, COLOUR, GLINT_ALPHA * glint);
    fillDot(context, x, y, radius, COLOUR, ALPHA);
  },
};
