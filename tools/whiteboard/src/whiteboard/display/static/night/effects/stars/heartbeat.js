// Heartbeat star (effects/): one star whose halo swells once a minute, over two and a
// half seconds, and fades again over four. A hero that stays on the board all night, or
// the brightest star that does.

import { safeRadius, skyToCanvas, starSkyPoint, starsWithin } from "../../geometry.js";
import { fillHalo } from "../../paint.js";
import { pick } from "../../random.js";
import { STAR_COLOURS } from "../../sky.js";
import { envelope } from "../../timing.js";

const PERIOD_S = 60;
const BEAT = { rise: 2.5, hold: 0.5, fall: 4 };
const HALO_RADIUS = [6, 14]; // of the star's radius, at rest and at the top of a beat
const HALO_ALPHA = 0.6;

export default {
  name: "heartbeat-star",
  family: "heartbeat",
  build(next, sky) {
    const safe = starsWithin(sky, safeRadius(sky));
    const heroes = safe.filter((star) => star.hero);
    const star = heroes.length ? pick(next, heroes) : brightest(safe.length ? safe : sky.stars);
    return {
      star: { ...starSkyPoint(star), radius: star.radius, rgb: STAR_COLOURS[star.colour].rgb },
      offset: next() * PERIOD_S,
    };
  },
  draw(context, state, frame) {
    const local = (frame.t + state.offset) % PERIOD_S;
    const beat = envelope(local, 0, BEAT);
    if (beat <= 0) return;
    const [rest, peak] = HALO_RADIUS;
    const { x, y } = skyToCanvas(state.star.x, state.star.y, frame);
    const radius = state.star.radius * frame.px * (rest + (peak - rest) * beat);
    fillHalo(context, x, y, radius, state.star.rgb, HALO_ALPHA * beat);
  },
};

function brightest(stars) {
  return stars.reduce((best, star) => (star.brightness > best.brightness ? star : best));
}
