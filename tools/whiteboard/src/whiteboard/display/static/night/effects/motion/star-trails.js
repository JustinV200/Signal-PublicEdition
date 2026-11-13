// Star trails (effects/): a short faint arc behind each hero star along the sky's turn,
// fading towards its tail, like a long exposure. Drawn behind the stars.

import { isInView, placeStar } from "../../geometry.js";
import { lightCss } from "../../paint.js";
import { STAR_COLOURS } from "../../sky.js";

const TRAIL_RAD = 0.035; // the arc behind a star, in radians about the pivot (2 degrees)
const SEGMENTS = 4; // the arc is drawn in steps of falling alpha
const TRAIL_ALPHA = 0.3; // at the star, times its brightness

export default {
  name: "star-trails",
  family: "rotation",
  layer: "behind",
  build(next, sky) {
    return { heroes: sky.stars.filter((star) => star.hero) };
  },
  draw(context, state, frame) {
    context.lineCap = "round";
    for (const star of state.heroes) {
      const { x, y } = placeStar(star, frame);
      if (!isInView(x, y, frame)) continue;
      const angle = Math.atan2(y - frame.pivotY, x - frame.pivotX);
      const rgb = STAR_COLOURS[star.colour].rgb;
      context.lineWidth = star.radius * frame.px;
      for (let i = 0; i < SEGMENTS; i++) {
        const from = angle - (TRAIL_RAD * (i + 1)) / SEGMENTS;
        const to = angle - (TRAIL_RAD * i) / SEGMENTS;
        context.strokeStyle = lightCss(rgb, TRAIL_ALPHA * star.brightness * (1 - i / SEGMENTS));
        context.beginPath();
        context.arc(frame.pivotX, frame.pivotY, star.r * frame.scale, from, to);
        context.stroke();
      }
    }
  },
};
