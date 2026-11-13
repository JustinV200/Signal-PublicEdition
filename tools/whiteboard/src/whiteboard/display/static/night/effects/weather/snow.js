// Snow (effects/): 100 to 140 soft flakes in three depth tiers (bigger is nearer and faster)
// falling with a gentle sway, wrapping from the bottom to the top. Drawn in front of the stars.

import { fillDot } from "../../paint.js";
import { between, pickWeighted } from "../../random.js";

const FLAKES = [100, 140];
// Depth tiers, far to near: radius at 1080p, fall speed (of the height per second, so
// a flake crosses the board in 20 to 60 s) and share of the flakes. Nearer is bigger and faster.
const TIERS = [
  { radiusPx: 2.5, speed: [0.017, 0.025], weight: 5 },
  { radiusPx: 3.2, speed: [0.025, 0.036], weight: 3 },
  { radiusPx: 4, speed: [0.036, 0.05], weight: 2 },
];
const TIER_WEIGHTS = TIERS.map((tier) => tier.weight);
const SWAY = 0.012; // of the width
const SWAY_S = [5, 9];
const COLOUR = [1, 0.9, 0.8]; // soft white-warm
const ALPHA = 0.95; // the cap in paint.js limits the channels; this is just near full

export default {
  name: "snow",
  family: "snow",
  build(next) {
    const flakes = [];
    const count = Math.round(between(next, ...FLAKES));
    for (let i = 0; i < count; i++) {
      const tier = TIERS[pickWeighted(next, TIER_WEIGHTS)];
      flakes.push({
        x: next(),
        y: next(),
        radiusPx: tier.radiusPx,
        speed: between(next, ...tier.speed),
        sway: { period: between(next, ...SWAY_S), phase: next() * 2 * Math.PI },
      });
    }
    return { flakes };
  },
  draw(context, state, frame) {
    for (const flake of state.flakes) {
      const fallen = flake.y + flake.speed * frame.t;
      const y = (fallen - Math.floor(fallen)) * frame.height;
      const sway = SWAY * Math.sin((2 * Math.PI * frame.t) / flake.sway.period + flake.sway.phase);
      fillDot(context, (flake.x + sway) * frame.width, y, flake.radiusPx * frame.px, COLOUR, ALPHA);
    }
  },
};
