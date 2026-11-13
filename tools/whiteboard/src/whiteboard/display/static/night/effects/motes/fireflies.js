// Fireflies (effects/): a handful of amber points low on the board, each glowing up over
// two and a half seconds and fading over three, on its own slow rhythm, wandering a little.

import { fillDot, fillHalo } from "../../paint.js";
import { between } from "../../random.js";
import { envelope } from "../../timing.js";

const COUNT = [6, 10];
const ZONE_X = [0.05, 0.95]; // of the width
const ZONE_Y = [0.78, 0.97]; // of the height
const BLINK_S = [10, 24]; // one glow per this long
const GLOW = { rise: 2.5, hold: 1, fall: 3 };
const COLOUR = [1, 0.75, 0.25];
const RADIUS_PX = 1.8; // at 1080p
const HALO_RADIUS = 4; // of the point's radius
const HALO_ALPHA = 0.45;
const WANDER = [0.012, 0.006]; // of the width and height
const WANDER_S = [9, 15];

export default {
  name: "fireflies",
  family: "fireflies",
  build(next) {
    const flies = [];
    const count = Math.round(between(next, ...COUNT));
    for (let i = 0; i < count; i++) {
      const period = between(next, ...BLINK_S);
      flies.push({
        x: between(next, ...ZONE_X),
        y: between(next, ...ZONE_Y),
        period,
        offset: next() * period,
        wander: { period: between(next, ...WANDER_S), phase: next() * 2 * Math.PI },
      });
    }
    return { flies };
  },
  draw(context, state, frame) {
    const radius = RADIUS_PX * frame.px;
    for (const fly of state.flies) {
      const glow = envelope((frame.t + fly.offset) % fly.period, 0, GLOW);
      if (glow <= 0) continue;
      const wave = (2 * Math.PI * frame.t) / fly.wander.period + fly.wander.phase;
      const x = (fly.x + WANDER[0] * Math.sin(wave)) * frame.width;
      const y = (fly.y + WANDER[1] * Math.sin(wave * 0.7)) * frame.height;
      fillHalo(context, x, y, radius * HALO_RADIUS, COLOUR, HALO_ALPHA * glow);
      fillDot(context, x, y, radius, COLOUR, glow);
    }
  },
};
