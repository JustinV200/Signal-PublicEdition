// Draws one frame of the night sky (night.js) onto a 2D canvas context: the Milky Way
// band with its nebulae, the effects behind the stars, the stars with a halo on the
// brightest, the moon, the effects in front, and any meteor in flight. Every light goes
// through paint.js, whose per-channel cap no blending can exceed.

import { enterBandFrame, isInView, placeFrame, placeStar } from "./geometry.js";
import { drawMoon } from "./moon.js";
import { fillDot, fillHalo, fillSoftDisk, lightCss, mixRgb } from "./paint.js";
import { NEBULA_STRETCH, SKY_RADIUS, STAR_COLOURS } from "./sky.js";
import { swell } from "./timing.js";

const GLOW_PEAK = 0.5; // of the cap, on the band's centre line
// [position, weight]: a narrow bright core on the centre line, dim shoulders in the edge hue.
const GLOW_STOPS = [[0, 0], [0.3, 0.25], [0.5, 1], [0.7, 0.25], [1, 0]];
const GLOW_HALF_WIDTH_SIGMAS = 2.5;
const NEBULA_PEAK = 0.5; // of the cap, at a cloud's centre
const NEBULA_CORE_PEAK = 0.9; // of the cap, at a cloud's dense core
const NEBULA_BREATH_DEPTH = 0.25; // a nebula's glow slowly fades by this much and back
const HALO_RADIUS = 8; // a hero star's halo, as a multiple of its radius
const HALO_PEAK = 0.55; // of the star's own alpha, at the halo's centre
const TWINKLE_DEPTH = 0.6; // a twinkling star dips to 40% of its brightness
const METEOR_COLOUR = [1, 0.86, 0.64]; // warm white, per channel in [0, 1]
const METEOR_PEAK = 0.85; // of the cap, mid-flight
const METEOR_TAIL = 0.6; // the visible tail, as a fraction of the path length
const METEOR_WIDTH_PX = 1.5; // at 1080p

/**
 * Draw one frame. `frame` is {t, rotation, meteor, width, height, zoom?, bandGain?,
 * nebulaTints?, effects?, moon?}: the sky time in seconds, the sky's turn in radians,
 * the meteor in flight or null, the canvas size in pixels, and what the effects adjust
 * (the zoom about the pivot, the band's glow, tints {rgbs, amount} with one rgb per
 * cloud) plus the built effects [{effect, state}] and the night's moon.
 */
export function drawFrame(context, sky, frame) {
  context.fillStyle = "#000";
  context.fillRect(0, 0, frame.width, frame.height);
  const placed = placeFrame(sky, frame);
  drawBand(context, sky, placed);
  drawEffects(context, placed, "behind");
  drawStars(context, sky, placed);
  if (frame.moon) drawMoon(context, frame.moon, placed);
  drawEffects(context, placed, "front");
  if (frame.meteor) drawMeteor(context, frame.meteor, placed);
}

// The effects of one layer, each inside its own save/restore so none leaks a transform.
function drawEffects(context, frame, layer) {
  for (const { effect, state } of frame.effects ?? []) {
    if (!effect.draw || (effect.layer ?? "front") !== layer) continue;
    context.save();
    effect.draw(context, state, frame);
    context.restore();
  }
}

// The band's glow and its nebulae, turned with the sky. In the band's frame the glow's
// gradient runs along x and the band itself along y. The core hue sits on the centre
// line and the edge hue on the shoulders.
function drawBand(context, { band, nebulae }, frame) {
  const centre = band.offset * frame.scale;
  const halfWidth = GLOW_HALF_WIDTH_SIGMAS * band.spread * frame.scale;
  const [core, edge] = band.hues;
  const gain = GLOW_PEAK * band.glow * (frame.bandGain ?? 1);
  const gradient = context.createLinearGradient(centre - halfWidth, 0, centre + halfWidth, 0);
  for (const [position, weight] of GLOW_STOPS) {
    const hue = weight === 1 ? core : edge;
    gradient.addColorStop(position, lightCss(hue.rgb, weight * gain));
  }
  const extent = SKY_RADIUS * frame.scale;
  context.save();
  enterBandFrame(context, { band }, frame);
  context.fillStyle = gradient;
  context.fillRect(centre - halfWidth, -extent, 2 * halfWidth, 2 * extent);
  nebulae.forEach((nebula, i) => drawNebula(context, nebula, frame, frame.nebulaTints?.rgbs[i]));
  context.restore();
}

// A soft oval of colour in the band's frame, stretched along the band, that breathes,
// with a small dense core in a second hue where the colour is strongest. `tintRgb`, if
// given, is the hue the cloud is being faded towards by `frame.nebulaTints.amount`.
function drawNebula(context, nebula, frame, tintRgb) {
  const radius = nebula.radius * frame.scale;
  const breath = 1 - NEBULA_BREATH_DEPTH * swell(frame.t, nebula.breath);
  const rgb = tintRgb ? mixRgb(nebula.rgb, tintRgb, frame.nebulaTints.amount) : nebula.rgb;
  context.save();
  context.translate(nebula.across * frame.scale, nebula.along * frame.scale);
  context.scale(1, NEBULA_STRETCH);
  fillSoftDisk(context, radius, rgb, NEBULA_PEAK * breath);
  fillSoftDisk(context, radius * nebula.core.radius, nebula.core.rgb, NEBULA_CORE_PEAK * breath);
  context.restore();
}

// Place every star for this rotation and draw the ones in view, each in its own colour.
function drawStars(context, sky, frame) {
  for (const star of sky.stars) {
    const { x, y } = placeStar(star, frame);
    if (!isInView(x, y, frame)) continue;
    const dip = star.twinkle ? TWINKLE_DEPTH * swell(frame.t, star.twinkle) : 0;
    const alpha = star.brightness * (1 - dip);
    const radius = star.radius * frame.px;
    const rgb = STAR_COLOURS[star.colour].rgb;
    if (star.hero) fillHalo(context, x, y, radius * HALO_RADIUS, rgb, alpha * HALO_PEAK);
    fillDot(context, x, y, radius, rgb, alpha);
  }
}

// A short streak that fades in and out over its flight, brightest at the head. Drawn in
// the frame rather than the turning sky, since meteors burn below the stars.
function drawMeteor(context, meteor, frame) {
  const progress = (frame.t - meteor.start) / meteor.duration;
  const envelope = Math.sin(Math.PI * progress) * METEOR_PEAK;
  const travelled = meteor.length * progress * frame.scale;
  const tail = Math.min(travelled, METEOR_TAIL * meteor.length * frame.scale);
  const headX = meteor.x * frame.width + meteor.dx * travelled;
  const headY = meteor.y * frame.height + meteor.dy * travelled;
  const tailX = headX - meteor.dx * tail;
  const tailY = headY - meteor.dy * tail;
  const gradient = context.createLinearGradient(tailX, tailY, headX, headY);
  gradient.addColorStop(0, lightCss(METEOR_COLOUR, 0));
  gradient.addColorStop(1, lightCss(METEOR_COLOUR, envelope));
  context.strokeStyle = gradient;
  context.lineWidth = METEOR_WIDTH_PX * frame.px;
  context.lineCap = "round";
  context.beginPath();
  context.moveTo(tailX, tailY);
  context.lineTo(headX, headY);
  context.stroke();
}
