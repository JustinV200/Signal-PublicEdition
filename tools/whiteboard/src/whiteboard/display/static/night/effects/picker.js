// Picks a night's effects (effects/index.js): 3 or 4 from the registry, never two of one
// family, from the date seed alone, so the same night always gets the same picks.

import { between, mulberry32, shuffle } from "../random.js";

export const PICK_COUNT = [3, 4]; // effects a night gets, inclusive
const PICK_MIX = 0x7f4a7c15; // keeps the picks' stream apart from the sky's and the meteors'

/**
 * The effects for a seed, from `registry` (each {name, family, ...}): a seeded shuffle,
 * walked until 3 or 4 are taken, skipping any whose family is already taken.
 */
export function pickEffects(seed, registry) {
  const next = mulberry32((seed ^ PICK_MIX) >>> 0);
  const [fewest, most] = PICK_COUNT;
  const count = Math.floor(between(next, fewest, most + 1));
  const families = new Set();
  const picks = [];
  for (const effect of shuffle(next, registry)) {
    if (picks.length === count) break;
    if (families.has(effect.family)) continue;
    families.add(effect.family);
    picks.push(effect);
  }
  return picks;
}
