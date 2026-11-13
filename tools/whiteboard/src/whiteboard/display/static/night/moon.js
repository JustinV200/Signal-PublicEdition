// The moon, part of every night's sky (night.js): its real phase for the night's date,
// from the mean synodic month and nothing else (no network, no lookup), drawn as a tiny
// crescent or disc that drifts across the top of the board over the night, with a soft
// breathing halo. A new moon shows nothing, which is the real phase.

import { fillHalo, lightCss } from "./paint.js";
import { nightProgress, swell } from "./timing.js";

// A reference new moon, 2000-01-06 18:14 UTC, and the mean synodic month in days. The
// mean phase is within about a day of the true one, which is all a 15 px moon can show.
const REFERENCE_NEW_MOON_MS = Date.UTC(2000, 0, 6, 18, 14);
const SYNODIC_MONTH_DAYS = 29.530588853;
const DAY_MS = 86400000;
const LIT_COLOUR = [1, 0.9, 0.7];
const LIT_ALPHA = 0.9;
const NEW_MOON_LIT = 0.02; // lit fraction under which nothing shows (about a day each side)
const RADIUS_PX = 15; // at 1080p
const HALO_RADIUS = 4; // of the moon's radius
const HALO_ALPHA = 0.3; // at the centre, for a full moon; a crescent's is dimmer
const HALO_FLOOR = 0.4; // a crescent still gets this share of the full moon's halo
const HALO_BREATH_S = 45;
const HALO_BREATH_DEPTH = 0.4;
const DRIFT_X = [0.12, 0.88]; // of the width, over the night
const ARC_TOP = 0.08; // of the height, mid-night
const ARC_SIDES = 0.16; // of the height, at dusk and dawn

/**
 * The moon's phase for a YYYYMMDD seed, in [0, 1): 0 is new, 0.5 full, under 0.5 waxing.
 * Taken at the night's midnight by the PC's local clock: the start of the day after the
 * evening the night began.
 */
export function moonPhase(seed) {
  const year = Math.floor(seed / 10000);
  const month = Math.floor(seed / 100) % 100;
  const day = seed % 100;
  const midnight = new Date(year, month - 1, day + 1).getTime();
  const months = (midnight - REFERENCE_NEW_MOON_MS) / DAY_MS / SYNODIC_MONTH_DAYS;
  return months - Math.floor(months);
}

/**
 * The night's moon for a seed: {phase, lit} with `lit` the lit fraction of the disc.
 */
export function buildMoon(seed) {
  const phase = moonPhase(seed);
  return { phase, lit: (1 - Math.cos(2 * Math.PI * phase)) / 2 };
}

/**
 * Draw the moon for this frame (a placed frame, see geometry.js): nothing on a new moon.
 */
export function drawMoon(context, moon, frame) {
  if (moon.lit < NEW_MOON_LIT) return;
  const progress = nightProgress(frame.t);
  const x = (DRIFT_X[0] + (DRIFT_X[1] - DRIFT_X[0]) * progress) * frame.width;
  const y = (ARC_SIDES - (ARC_SIDES - ARC_TOP) * Math.sin(Math.PI * progress)) * frame.height;
  const radius = RADIUS_PX * frame.px;
  const breath = 1 - HALO_BREATH_DEPTH * swell(frame.t, { period: HALO_BREATH_S, phase: 0 });
  const haloAlpha = HALO_ALPHA * (HALO_FLOOR + (1 - HALO_FLOOR) * moon.lit) * breath;
  fillHalo(context, x, y, radius * HALO_RADIUS, LIT_COLOUR, haloAlpha);
  context.save();
  context.translate(x, y);
  drawDisc(context, moon, radius);
  context.restore();
}

// The lit disc with its dark side painted over: the half away from the sun, then the
// terminator's ellipse (dark for a crescent, lit for a gibbous moon). Waxing is lit on
// the right, as seen from the northern hemisphere.
function drawDisc(context, moon, radius) {
  const waxing = moon.phase < 0.5;
  const terminator = radius * Math.abs(Math.cos(2 * Math.PI * moon.phase));
  const crescent = moon.lit < 0.5;
  context.fillStyle = lightCss(LIT_COLOUR, LIT_ALPHA);
  context.beginPath();
  context.arc(0, 0, radius, 0, 2 * Math.PI);
  context.fill();
  context.fillStyle = "#000";
  context.beginPath();
  context.arc(0, 0, radius, Math.PI / 2, (3 * Math.PI) / 2, !waxing);
  context.fill();
  context.fillStyle = crescent ? "#000" : lightCss(LIT_COLOUR, LIT_ALPHA);
  context.beginPath();
  context.ellipse(0, 0, terminator, radius, 0, 0, 2 * Math.PI);
  context.fill();
}
