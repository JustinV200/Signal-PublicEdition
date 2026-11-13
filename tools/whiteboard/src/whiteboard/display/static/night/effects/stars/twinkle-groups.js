// Twinkle groups (effects/): a few clusters of neighbouring stars that pulse together,
// each cluster on its own slow beat, as a soft glow over every member. Each cluster is
// anchored on a star that stays on the board all night.

import { safeRadius, skyToCanvas, starSkyPoint, starsWithin } from "../../geometry.js";
import { fillHalo } from "../../paint.js";
import { between, pick } from "../../random.js";
import { STAR_COLOURS } from "../../sky.js";
import { swell } from "../../timing.js";

const GROUPS = 3;
const ANCHOR_MIN_BRIGHTNESS = 0.4;
const GROUP_RADIUS = 0.18; // sky units around the anchor
const MAX_MEMBERS = 12;
const PERIOD_S = [5, 9];
const PULSE_RADIUS = 3.5; // of the star's radius
const PULSE_ALPHA = 0.5;

export default {
  name: "twinkle-groups",
  family: "twinkle",
  build(next, sky) {
    const safe = starsWithin(sky, safeRadius(sky));
    const anchors = safe.filter((star) => star.brightness >= ANCHOR_MIN_BRIGHTNESS);
    const groups = [];
    for (let i = 0; i < GROUPS && anchors.length; i++) {
      const centre = starSkyPoint(pick(next, anchors));
      const members = sky.stars
        .filter((star) => {
          const { x, y } = starSkyPoint(star);
          return Math.hypot(x - centre.x, y - centre.y) <= GROUP_RADIUS;
        })
        .slice(0, MAX_MEMBERS)
        .map((star) => ({ ...starSkyPoint(star), radius: star.radius, rgb: STAR_COLOURS[star.colour].rgb }));
      groups.push({ members, beat: { period: between(next, ...PERIOD_S), phase: next() * 2 * Math.PI } });
    }
    return { groups };
  },
  draw(context, state, frame) {
    for (const group of state.groups) {
      const glow = PULSE_ALPHA * (1 - swell(frame.t, group.beat));
      for (const member of group.members) {
        const { x, y } = skyToCanvas(member.x, member.y, frame);
        fillHalo(context, x, y, member.radius * frame.px * PULSE_RADIUS, member.rgb, glow);
      }
    }
  },
};
