// The night's meteors (night.js): a seeded schedule of occasional, slow, faint streaks.
// It is laid out from the start of the sky-time day (night.js), not from when the page
// loaded, so a reload in the night shows the same meteors at the same moments.

import { between, mulberry32 } from "./random.js";

const GAP_S = [60, 180]; // from one meteor's end to the next one's start
const DURATION_S = [1.4, 2.4];
const LENGTH = [0.12, 0.28]; // of the path, in sky units (canvas heights)
const DIRECTION = [0.1 * Math.PI, 0.9 * Math.PI]; // always falling, never straight up
const START_X = [-0.1, 1.1]; // fractions of the width; a little outside the frame is fine
const START_Y = [-0.1, 0.6]; // of the height; high enough for the fall to stay in view
const SEED_MIX = 0x9e3779b9; // keeps the meteor stream apart from the star field's
const DAY_S = 86400;

/**
 * The meteor schedule for a seed. `at(t)` takes sky time in seconds (night.js) and
 * returns the meteor in flight as {x, y, dx, dy, length, start, duration} (x, y are
 * fractions of the canvas width and height; dx, dy the unit direction), or null when
 * the sky is quiet. Each new sky-time day restarts the stream from its first second.
 */
export function createMeteorSchedule(seed) {
  let day = null;
  let next = null;
  let meteor = null;
  return {
    at(t) {
      const today = Math.floor(t / DAY_S);
      if (today !== day) {
        day = today;
        next = mulberry32((seed ^ SEED_MIX) >>> 0);
        meteor = nextMeteor(next, today * DAY_S);
      }
      while (meteor.start + meteor.duration < t) {
        meteor = nextMeteor(next, meteor.start + meteor.duration);
      }
      return t >= meteor.start ? meteor : null;
    },
  };
}

function nextMeteor(next, after) {
  const start = after + between(next, ...GAP_S);
  const direction = between(next, ...DIRECTION);
  return {
    start,
    duration: between(next, ...DURATION_S),
    length: between(next, ...LENGTH),
    x: between(next, ...START_X),
    y: between(next, ...START_Y),
    dx: Math.cos(direction),
    dy: Math.sin(direction),
  };
}
