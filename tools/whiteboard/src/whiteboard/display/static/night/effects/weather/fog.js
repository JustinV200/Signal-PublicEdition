// Low fog (effects/): a warm-grey haze along the bottom of the board that slowly rises
// and settles, with a few wide lumps drifting sideways. Drawn in front of the stars.

import { fillSoftDisk, lightCss } from "../../paint.js";
import { between } from "../../random.js";
import { swell } from "../../timing.js";

const HEIGHT = [0.14, 0.22]; // of the frame's height, at its fullest
const RISE_S = [150, 240];
const RISE_DEPTH = 0.35; // it settles by this much at the bottom of a cycle
const COLOUR = [1, 0.85, 0.7];
// Faint on purpose: the fog covers a fifth of the board, so at twice this it alone
// doubled a night's light.
const ALPHA = 0.2; // at the very bottom
const LUMPS = 3;
const LUMP_RADIUS = [0.25, 0.4]; // of the width
const LUMP_FLATNESS = 0.35; // a lump's height, as a share of its width
const LUMP_DRIFT = 0.05; // of the width
const LUMP_DRIFT_S = [90, 150];
const LUMP_ALPHA = 0.1;

export default {
  name: "fog",
  family: "weather",
  build(next) {
    const lumps = [];
    for (let i = 0; i < LUMPS; i++) {
      lumps.push({
        x: next(),
        radius: between(next, ...LUMP_RADIUS),
        drift: { period: between(next, ...LUMP_DRIFT_S), phase: next() * 2 * Math.PI },
      });
    }
    return {
      height: between(next, ...HEIGHT),
      rise: { period: between(next, ...RISE_S), phase: next() * 2 * Math.PI },
      lumps,
    };
  },
  draw(context, state, frame) {
    const depth = state.height * (1 - RISE_DEPTH * swell(frame.t, state.rise)) * frame.height;
    const gradient = context.createLinearGradient(0, frame.height, 0, frame.height - depth);
    gradient.addColorStop(0, lightCss(COLOUR, ALPHA));
    gradient.addColorStop(1, lightCss(COLOUR, 0));
    context.fillStyle = gradient;
    context.fillRect(0, frame.height - depth, frame.width, depth);
    for (const lump of state.lumps) {
      const drift = LUMP_DRIFT * Math.sin((2 * Math.PI * frame.t) / lump.drift.period + lump.drift.phase);
      context.save();
      context.translate((lump.x + drift) * frame.width, frame.height);
      context.scale(1, LUMP_FLATNESS);
      fillSoftDisk(context, lump.radius * frame.width, COLOUR, LUMP_ALPHA);
      context.restore();
    }
  },
};
