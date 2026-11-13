// Dust motes (effects/): a few dozen small specks in front of the nebulae, each in its
// cloud's core hue, drifting slowly back and forth in the band's frame.

import { enterBandFrame } from "../../geometry.js";
import { fillDot } from "../../paint.js";
import { between, pick } from "../../random.js";
import { NEBULA_STRETCH } from "../../sky.js";

const COUNT = [20, 40];
const RADIUS_PX = 1.3; // at 1080p
const ALPHA = 0.7;
const DRIFT = 0.03; // sky units, each way
const DRIFT_S = [60, 120];

export default {
  name: "dust-motes",
  family: "motes",
  build(next, sky) {
    const motes = [];
    const count = Math.round(between(next, ...COUNT));
    for (let i = 0; i < count; i++) {
      const nebula = pick(next, sky.nebulae);
      const angle = next() * 2 * Math.PI;
      const distance = nebula.radius * Math.sqrt(next()); // even over the cloud's oval
      motes.push({
        across: nebula.across + distance * Math.cos(angle),
        along: nebula.along + distance * Math.sin(angle) * NEBULA_STRETCH,
        heading: next() * 2 * Math.PI,
        rgb: nebula.core.rgb,
        drift: { period: between(next, ...DRIFT_S), phase: next() * 2 * Math.PI },
      });
    }
    return { band: sky.band, motes };
  },
  draw(context, state, frame) {
    enterBandFrame(context, { band: state.band }, frame);
    const radius = RADIUS_PX * frame.px;
    for (const mote of state.motes) {
      const shift = DRIFT * Math.sin((2 * Math.PI * frame.t) / mote.drift.period + mote.drift.phase);
      const x = (mote.across + shift * Math.cos(mote.heading)) * frame.scale;
      const y = (mote.along + shift * Math.sin(mote.heading)) * frame.scale;
      fillDot(context, x, y, radius, mote.rgb, ALPHA);
    }
  },
};
