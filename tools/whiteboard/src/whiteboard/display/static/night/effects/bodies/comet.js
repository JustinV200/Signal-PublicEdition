// Comet (effects/): about every twenty minutes a gold head with a long soft tail crosses
// the board over a minute and a half, fading in and out over fifteen seconds each way.

import { crossing, crossingPoint } from "../../geometry.js";
import { fillDot, fillHalo, lightCss } from "../../paint.js";
import { between, childSeed } from "../../random.js";
import { envelope, eventAt } from "../../timing.js";

const PERIOD_S = [1000, 1400];
const CROSSING_S = 90;
const FADE = { rise: 15, hold: 60, fall: 15 };
const PATH = { heights: [0.1, 0.9], margin: 0.15 }; // enters and leaves well outside the frame
const COLOUR = [1, 0.82, 0.4]; // gold
const HEAD_RADIUS_PX = 2.6; // at 1080p
const HEAD_HALO = 4; // of the head's radius
const HEAD_HALO_ALPHA = 0.5;
const TAIL_LENGTH = 0.12; // of the height
const TAIL_WIDTH_PX = 6; // at 1080p
const TAIL_ALPHA = 0.45; // at the head

export default {
  name: "comet",
  family: "comet",
  build(next) {
    return { schedule: { period: between(next, ...PERIOD_S), seed: childSeed(next) } };
  },
  draw(context, state, frame) {
    const event = eventAt(frame.t, state.schedule, CROSSING_S);
    if (!event) return;
    const fade = envelope(event.local, 0, FADE);
    const path = crossing(event.next, PATH);
    const { x, y, dx, dy } = crossingPoint(path, event.local / CROSSING_S, frame);
    const tailX = x - dx * TAIL_LENGTH * frame.height;
    const tailY = y - dy * TAIL_LENGTH * frame.height;
    const gradient = context.createLinearGradient(x, y, tailX, tailY);
    gradient.addColorStop(0, lightCss(COLOUR, TAIL_ALPHA * fade));
    gradient.addColorStop(1, lightCss(COLOUR, 0));
    context.strokeStyle = gradient;
    context.lineWidth = TAIL_WIDTH_PX * frame.px;
    context.lineCap = "round";
    context.beginPath();
    context.moveTo(x, y);
    context.lineTo(tailX, tailY);
    context.stroke();
    const radius = HEAD_RADIUS_PX * frame.px;
    fillHalo(context, x, y, radius * HEAD_HALO, COLOUR, HEAD_HALO_ALPHA * fade);
    fillDot(context, x, y, radius, COLOUR, fade);
  },
};
