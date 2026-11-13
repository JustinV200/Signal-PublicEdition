// Constellations (effects/): faint warm lines joining a few of the sky's brighter stars,
// one figure at a time, fading in and out every few minutes. Each figure starts at a
// bright star that stays on the board all night; the chain may reach a little beyond,
// where a line's far end can set at the edge like a real figure. Drawn behind the stars
// so they sit on the line ends.

import { safeRadius, skyToCanvas, starSkyPoint, starsWithin } from "../../geometry.js";
import { lightCss } from "../../paint.js";
import { between, pick } from "../../random.js";
import { cycleAt, envelope } from "../../timing.js";

const FIGURES = 2; // shown in turn, one per cycle, from two different anchors
const ANCHOR_MIN_BRIGHTNESS = 0.6; // a figure starts at a bright star
const MEMBER_MIN_BRIGHTNESS = 0.3;
const REACH = [0.06, 0.3]; // the next star is the nearest at least this far, at most this far
const MEMBERS = [5, 8];
const PERIOD_S = [240, 360];
const FADE = { rise: 20, hold: 60, fall: 20 };
const LINE_COLOUR = [1, 0.86, 0.64];
const LINE_ALPHA = 0.6;
const LINE_WIDTH_PX = 1.6; // at 1080p

export default {
  name: "constellations",
  family: "constellations",
  layer: "behind",
  build(next, sky) {
    const reach = safeRadius(sky) + REACH[1];
    const members = starsWithin(sky, reach)
      .filter((star) => star.brightness >= MEMBER_MIN_BRIGHTNESS).map(starSkyPoint);
    let anchors = starsWithin(sky, safeRadius(sky))
      .filter((star) => star.brightness >= ANCHOR_MIN_BRIGHTNESS).map(starSkyPoint);
    const figures = [];
    for (let i = 0; i < FIGURES && anchors.length; i++) {
      const anchor = pick(next, anchors);
      anchors = anchors.filter((point) => point !== anchor);
      figures.push(chain(next, anchor, members));
    }
    return { figures, period: between(next, ...PERIOD_S) };
  },
  draw(context, state, frame) {
    if (!state.figures.length) return;
    const { index, local } = cycleAt(frame.t, state.period);
    const alpha = LINE_ALPHA * envelope(local, 0, FADE);
    if (alpha <= 0) return;
    context.strokeStyle = lightCss(LINE_COLOUR, alpha);
    context.lineWidth = LINE_WIDTH_PX * frame.px;
    context.beginPath();
    state.figures[index % state.figures.length].forEach((point, i) => {
      const { x, y } = skyToCanvas(point.x, point.y, frame);
      if (i === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();
  },
};

// A chain from the anchor: each step goes to the nearest unused star within reach.
function chain(next, anchor, candidates) {
  const figure = [anchor];
  const count = Math.round(between(next, ...MEMBERS));
  const [tooClose, reach] = REACH;
  while (figure.length < count) {
    const last = figure[figure.length - 1];
    let best = null;
    let bestDistance = reach;
    for (const point of candidates) {
      const distance = Math.hypot(point.x - last.x, point.y - last.y);
      if (distance < tooClose || distance >= bestDistance || figure.includes(point)) continue;
      best = point;
      bestDistance = distance;
    }
    if (!best) break;
    figure.push(best);
  }
  return figure;
}
