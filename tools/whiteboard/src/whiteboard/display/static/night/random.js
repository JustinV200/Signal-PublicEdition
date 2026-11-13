// Seeded random numbers for the night sky (night.js). Everything the sky looks like comes
// from these and never from Math.random(), so one seed always gives the same sky.

const UINT32_RANGE = 4294967296;
const CHILD_MIX = 0x9e3779b9; // spreads child seeds apart (the golden-ratio constant)

// A mulberry32 generator: `next()` returns a float in [0, 1). The seed is any integer.
export function mulberry32(seed) {
  let state = seed >>> 0;
  return function next() {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = state;
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / UINT32_RANGE;
  };
}

// A float in [low, high) from the next draw.
export function between(next, low, high) {
  return low + (high - low) * next();
}

// One entry of `list`, from the next draw.
export function pick(next, list) {
  return list[Math.floor(next() * list.length)];
}

// An index into `weights` (relative, any scale), from the next draw: the chance of each
// index is its weight's share of the total.
export function pickWeighted(next, weights) {
  const total = weights.reduce((sum, weight) => sum + weight, 0);
  let remaining = next() * total;
  for (let index = 0; index < weights.length; index++) {
    remaining -= weights[index];
    if (remaining < 0) return index;
  }
  return weights.length - 1; // only when rounding leaves a hair of the total
}

// A standard normal draw (Box-Muller; uses two draws).
export function gaussian(next) {
  const radial = 1 - next(); // (0, 1], so the log stays finite
  const angle = next();
  return Math.sqrt(-2 * Math.log(radial)) * Math.cos(2 * Math.PI * angle);
}

// A new array with `list` in a seeded order (Fisher-Yates; one draw per entry).
export function shuffle(next, list) {
  const order = [...list];
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(next() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  return order;
}

// An integer seed for a sub-stream, from the next draw (for things that need their own
// generator later, like a schedule's events).
export function childSeed(next) {
  return Math.floor(next() * UINT32_RANGE);
}

// A generator for event `index` of the stream seeded by `seed`, so an event's details
// can be drawn without replaying every event before it.
export function eventRandom(seed, index) {
  return mulberry32((seed + Math.imul(index, CHILD_MIX)) >>> 0);
}
