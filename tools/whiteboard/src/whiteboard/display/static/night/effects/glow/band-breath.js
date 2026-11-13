// Milky Way breath (effects/): the band's glow swells and fades by a third over about
// ten minutes.

import { swell } from "../../timing.js";

const PERIOD_S = 600;
const DEPTH = 0.35; // the glow fades by this much at the bottom of a breath

export default {
  name: "band-breath",
  family: "milkyway",
  build(next) {
    return { breath: { period: PERIOD_S, phase: next() * 2 * Math.PI } };
  },
  adjust(state, frame) {
    return { bandGain: 1 - DEPTH * swell(frame.t, state.breath) };
  },
};
