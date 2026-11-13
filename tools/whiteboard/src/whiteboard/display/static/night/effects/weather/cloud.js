// Passing cloud (effects/): every ten minutes or so a thin cloud drifts across the board
// over three minutes, dimming the stars behind it, with a faint warm rim so its shape
// shows. Drawn in front of the stars.

import { crossing, crossingPoint } from "../../geometry.js";
import { fillHalo } from "../../paint.js";
import { between, childSeed } from "../../random.js";
import { eventAt } from "../../timing.js";

const PERIOD_S = [480, 720];
const CROSSING_S = 180;
const PUFFS = 5; // soft blobs that make the cloud
const PUFF_RADIUS = [0.08, 0.14]; // of the height
const PUFF_RISE = [-0.04, 0.04]; // each puff's offset from the cloud's line, of the height
const SPAN = 0.3; // the cloud's length, of the width
// Level, and starting a whole cloud's length outside the frame so it enters from nothing.
const PATH = { heights: [0.2, 0.7], margin: SPAN, level: true };
const SHADE = [0, 0, 0];
const SHADE_ALPHA = 0.8; // stars behind the cloud's centre dim to a fifth
const RIM_COLOUR = [1, 0.8, 0.6];
const RIM_RADIUS = 1.1; // of the puff's radius
const RIM_ALPHA = 0.12;

export default {
  name: "cloud",
  family: "weather",
  build(next) {
    return { schedule: { period: between(next, ...PERIOD_S), seed: childSeed(next) } };
  },
  draw(context, state, frame) {
    const event = eventAt(frame.t, state.schedule, CROSSING_S);
    if (!event) return;
    const path = crossing(event.next, PATH);
    const centre = crossingPoint(path, event.local / CROSSING_S, frame);
    for (let i = 0; i < PUFFS; i++) {
      const radius = between(event.next, ...PUFF_RADIUS) * frame.height;
      const x = centre.x + (i / (PUFFS - 1) - 0.5) * SPAN * frame.width;
      const y = centre.y + between(event.next, ...PUFF_RISE) * frame.height;
      fillHalo(context, x, y, radius * RIM_RADIUS, RIM_COLOUR, RIM_ALPHA);
      fillHalo(context, x, y, radius, SHADE, SHADE_ALPHA);
    }
  },
};
