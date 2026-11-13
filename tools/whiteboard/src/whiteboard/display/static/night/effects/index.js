// The night sky's effect pool (night.js): the registry of every effect, the picker, and
// the builder that turns a night's picks into drawable state. Each effect is one module
// exporting {name, family, layer?, build(next, sky), adjust?(state, frame),
// draw?(context, state, frame)}; see README.md for the contract.

import { mulberry32 } from "../random.js";
import comet from "./bodies/comet.js";
import satellite from "./bodies/satellite.js";
import aurora from "./glow/aurora.js";
import bandBreath from "./glow/band-breath.js";
import galaxies from "./glow/galaxies.js";
import hueCrossfade from "./glow/hue-crossfade.js";
import rotation from "./motion/rotation.js";
import starTrails from "./motion/star-trails.js";
import zoomOut from "./motion/zoom-out.js";
import dustMotes from "./motes/dust-motes.js";
import fireflies from "./motes/fireflies.js";
import { pickEffects } from "./picker.js";
import constellations from "./stars/constellations.js";
import heartbeat from "./stars/heartbeat.js";
import hourMarker from "./stars/hour-marker.js";
import planets from "./stars/planets.js";
import twinkleGroups from "./stars/twinkle-groups.js";
import cloud from "./weather/cloud.js";
import fog from "./weather/fog.js";
import snow from "./weather/snow.js";

export { pickEffects };

/** Every effect a night can pick from. */
export const EFFECTS = [
  constellations, planets, twinkleGroups, heartbeat, hourMarker,
  rotation, starTrails, zoomOut,
  bandBreath, hueCrossfade, aurora, galaxies,
  satellite, comet,
  cloud, fog, snow,
  fireflies, dustMotes,
];

const BUILD_MIX = 0x3c6ef372; // the effects' own random stream, apart from the sky's

/**
 * The built effects for a seed, [{effect, state}], for `chosen` (the night's picks by
 * default; pass EFFECTS to build every one, as the cap test does). Building draws from
 * one seeded stream in pick order, so one seed always builds the same states.
 */
export function buildEffects(seed, sky, chosen = pickEffects(seed, EFFECTS)) {
  const next = mulberry32((seed ^ BUILD_MIX) >>> 0);
  return chosen.map((effect) => ({ effect, state: effect.build(next, sky) }));
}
