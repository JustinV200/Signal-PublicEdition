// Hour-marker star (effects/): a steady gold star low on the board, fixed to the frame
// rather than the turning sky, whose halo swells on the hour and fades over the next
// two minutes.

import { fillDot, fillHalo } from "../../paint.js";
import { between } from "../../random.js";
import { envelope } from "../../timing.js";

const POSITION_X = [0.08, 0.92]; // of the width
const POSITION_Y = [0.8, 0.9]; // of the height
const COLOUR = [1, 0.78, 0.3]; // gold
const RADIUS_PX = 2.8; // at 1080p
const STEADY_HALO = 4; // of the star's radius
const STEADY_ALPHA = 0.35;
const HOUR_S = 3600; // sky time's hours start on the clock's (night.js)
const SWELL = { rise: 30, hold: 30, fall: 90 };
const SWELL_HALO = 16; // of the star's radius, at the top of the swell
const SWELL_ALPHA = 0.5;

export default {
  name: "hour-marker",
  family: "hour-marker",
  build(next) {
    return { x: between(next, ...POSITION_X), y: between(next, ...POSITION_Y) };
  },
  draw(context, state, frame) {
    const radius = RADIUS_PX * frame.px;
    const x = state.x * frame.width;
    const y = state.y * frame.height;
    const onTheHour = envelope(frame.t % HOUR_S, 0, SWELL);
    fillHalo(context, x, y, radius * STEADY_HALO, COLOUR, STEADY_ALPHA);
    if (onTheHour > 0) fillHalo(context, x, y, radius * SWELL_HALO, COLOUR, SWELL_ALPHA * onTheHour);
    fillDot(context, x, y, radius, COLOUR, 1);
  },
};
