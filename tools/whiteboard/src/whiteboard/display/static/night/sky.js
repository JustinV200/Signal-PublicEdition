// Builds the night sky for a seed (night.js): a pure function, so one seed is one sky.
// The sky is measured in sky units (1 = the canvas height) in a frame centred on a pivot
// point, around which the whole field turns during the night. Stars are kept in polar
// form (distance r, and the cos/sin of their angle) so a frame only needs one rotation
// angle to place them all. The Milky Way band and its nebulae are given in the band's
// own frame (across its normal, along its line), where draw.js paints them.

import { between, gaussian, mulberry32, pickWeighted } from "./random.js";

// Far enough from any pivot inside the frame to cover every corner of a 16:9 canvas,
// however far the sky has turned. shortcut: a board fit wider than ~1.86:1 leaves bare
// corners, raise it if the board is ever fitted that wide.
export const SKY_RADIUS = 1.9;

// Star colours, per channel in [0, 1] before paint.js applies the per-channel cap, and
// how common each is. Warm on purpose (warm white, amber and orange carry most of the
// field), with blue-white and cyan kept rare as accents: blue light is what keeps the
// sleeper awake, and warm colour is what shows against the projector's blue-grey floor.
export const STAR_COLOURS = [
  { name: "warm white", rgb: [1, 0.86, 0.64], weight: 0.4 },
  { name: "amber", rgb: [1, 0.62, 0.28], weight: 0.24 },
  { name: "orange", rgb: [1, 0.42, 0.18], weight: 0.12 },
  { name: "blue-white", rgb: [0.62, 0.76, 1], weight: 0.16 },
  { name: "cyan", rgb: [0.5, 0.9, 1], weight: 0.08 },
];
const STAR_WEIGHTS = STAR_COLOURS.map((colour) => colour.weight);

// Hues for the band and its nebulae, per channel in [0, 1], weighted warm. Saturated on
// purpose: one or two channels carry the glow, so it reads as colour without much light.
export const HUES = [
  { name: "crimson", rgb: [1, 0.2, 0.35], weight: 3 },
  { name: "magenta", rgb: [1, 0.25, 0.72], weight: 3 },
  { name: "amber", rgb: [1, 0.55, 0.12], weight: 3 },
  { name: "gold", rgb: [1, 0.78, 0.3], weight: 2 },
  { name: "violet", rgb: [0.6, 0.3, 1], weight: 1 },
  { name: "teal", rgb: [0.15, 0.85, 0.9], weight: 1 },
];

const PIVOT_RANGE = [0.1, 0.9]; // pivot, as a fraction of the width and of the height
const FIELD_STARS = [1600, 3200]; // across the whole disk; a 16:9 frame sees about 16%
const BAND_STARS = [250, 700];
const BAND_OFFSET = [-0.5, 0.5]; // distance of the band's centre line from the pivot
const BAND_SPREAD = [0.1, 0.22]; // sigma of the band's star scatter, in sky units
const BAND_GLOW = [0.7, 1]; // scales the band's glow between seeds
const BAND_DIMMING = 0.7; // band stars are smaller and fainter than the field
const NEBULAE = [2, 4]; // soft coloured clouds along the band
const NEBULA_ALONG = [-1, 1]; // where along the band, in sky units; most land in view
const NEBULA_RADIUS = [0.15, 0.32]; // in sky units
const NEBULA_CORE = [0.25, 0.4]; // the dense core's radius, as a fraction of the cloud's
export const NEBULA_STRETCH = 1.8; // a nebula is this much longer along the band than across
const NEBULA_BREATH_S = [25, 45]; // one slow swell and fade of a nebula's glow
// Faint stars below this were under the projector's black level and never showed; at
// this floor the faintest warm-white star is about 27/255 red, just above it.
const MIN_BRIGHTNESS = 0.25;
const BRIGHTNESS_SKEW = 2.2; // u^skew: most stars faint, a handful bright
const HERO_FRACTION = 0.025; // the brightest stars, drawn with a soft halo
const HERO_BRIGHTNESS = [0.85, 1];
const TWINKLE_FRACTION = 0.14;
const TWINKLE_PERIOD_S = [3, 8];
const STAR_RADIUS_PX = [0.7, 2.2]; // at 1080p; draw.js scales with the canvas height
const HERO_RADIUS_PX = [2.6, 3.4];

/**
 * Build the sky for an integer seed. Returns {seed, pivot, band, nebulae, stars}: `pivot`
 * {x, y} as fractions of the canvas width and height; `band` {normalAngle, offset,
 * spread, glow, hues: [core, edge]} with each hue {name, rgb}; each nebula {across,
 * along, radius, rgb, core: {radius, rgb}, breath: {period, phase}}; each star {r, cos,
 * sin, brightness, radius, colour (an index into STAR_COLOURS), hero, twinkle} with
 * `twinkle` null or {period, phase}. Throws TypeError when the seed isn't an integer.
 */
export function buildSky(seed) {
  if (!Number.isInteger(seed)) {
    throw new TypeError(`night sky seed must be an integer, got ${seed}`);
  }
  const next = mulberry32(seed);
  const pivot = { x: between(next, ...PIVOT_RANGE), y: between(next, ...PIVOT_RANGE) };
  const core = pickHue(next);
  const band = {
    normalAngle: next() * Math.PI,
    offset: between(next, ...BAND_OFFSET),
    spread: between(next, ...BAND_SPREAD),
    glow: between(next, ...BAND_GLOW),
    hues: [core, pickHue(next, core.rgb)],
  };
  const nebulaCount = Math.round(between(next, ...NEBULAE));
  const fieldCount = Math.round(between(next, ...FIELD_STARS));
  const bandCount = Math.round(between(next, ...BAND_STARS));
  const nebulae = [];
  for (let i = 0; i < nebulaCount; i++) nebulae.push(nebula(next, band));
  const stars = [];
  for (let i = 0; i < fieldCount; i++) stars.push(fieldStar(next));
  for (let i = 0; i < bandCount; i++) stars.push(bandStar(next, band));
  return { seed, pivot, band, nebulae, stars };
}

/**
 * A weighted hue from HUES, never the one whose rgb is `exceptRgb` (so a cloud's core
 * differs from its envelope, and a tint from the cloud it tints).
 */
export function pickHue(next, exceptRgb = null) {
  const choices = HUES.filter((hue) => hue.rgb !== exceptRgb);
  return choices[pickWeighted(next, choices.map((hue) => hue.weight))];
}

// A soft cloud on the band: scattered across it like its stars, anywhere along it, with
// a dense core in a second hue where the colour concentrates.
function nebula(next, band) {
  const hue = pickHue(next);
  return {
    across: band.offset + gaussian(next) * band.spread,
    along: between(next, ...NEBULA_ALONG),
    radius: between(next, ...NEBULA_RADIUS),
    rgb: hue.rgb,
    core: { radius: between(next, ...NEBULA_CORE), rgb: pickHue(next, hue.rgb).rgb },
    breath: { period: between(next, ...NEBULA_BREATH_S), phase: next() * 2 * Math.PI },
  };
}

// Spread evenly over the disk: sqrt keeps the density the same at every radius.
function fieldStar(next) {
  return makeStar(next, SKY_RADIUS * Math.sqrt(next()), next() * 2 * Math.PI, 1);
}

// Scattered about the band's centre line: `along` runs along the line and the gaussian
// `across` is the distance from it, measured along the band's normal.
function bandStar(next, band) {
  const along = between(next, -SKY_RADIUS, SKY_RADIUS);
  const across = band.offset + gaussian(next) * band.spread;
  const x = across * Math.cos(band.normalAngle) - along * Math.sin(band.normalAngle);
  const y = across * Math.sin(band.normalAngle) + along * Math.cos(band.normalAngle);
  return makeStar(next, Math.hypot(x, y), Math.atan2(y, x), BAND_DIMMING);
}

function makeStar(next, r, angle, dimming) {
  const hero = next() < HERO_FRACTION;
  const brightness = hero
    ? between(next, ...HERO_BRIGHTNESS)
    : Math.max(MIN_BRIGHTNESS, next() ** BRIGHTNESS_SKEW) * dimming;
  const twinkle = next() < TWINKLE_FRACTION
    ? { period: between(next, ...TWINKLE_PERIOD_S), phase: next() * 2 * Math.PI }
    : null;
  const [smallest, largest] = hero ? HERO_RADIUS_PX : STAR_RADIUS_PX;
  return {
    r,
    cos: Math.cos(angle),
    sin: Math.sin(angle),
    brightness,
    radius: smallest + (largest - smallest) * brightness,
    colour: pickWeighted(next, STAR_WEIGHTS),
    hero,
    twinkle,
  };
}
