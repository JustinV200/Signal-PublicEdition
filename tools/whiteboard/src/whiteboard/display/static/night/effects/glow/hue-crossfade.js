// Nebula hue cross-fade (effects/): each cloud drifts towards a second hue, never its
// own, and back over about five minutes; the dense cores keep their colour.

import { between } from "../../random.js";
import { pickHue } from "../../sky.js";
import { swell } from "../../timing.js";

const PERIOD_S = [240, 360];
const AMOUNT = 0.85; // how far towards the second hue at the top of the fade

export default {
  name: "hue-crossfade",
  family: "nebula-hue",
  build(next, sky) {
    return {
      rgbs: sky.nebulae.map((nebula) => pickHue(next, nebula.rgb).rgb),
      fade: { period: between(next, ...PERIOD_S), phase: next() * 2 * Math.PI },
    };
  },
  adjust(state, frame) {
    return { nebulaTints: { rgbs: state.rgbs, amount: AMOUNT * (1 - swell(frame.t, state.fade)) } };
  },
};
