// Time for the night sky (night.js): sky time, slow waves, fade envelopes and the night's
// progress, all pure functions of the clock, so a reload shows the same moment. Nothing
// here ever steps: every change in brightness is a ramp.

import { eventRandom } from "./random.js";

// Sky time counts seconds from 2023-11-14T17:00:00Z. Its days turn over at 17:00 UTC,
// midday in the owner's time zone, so a night's schedules never restart mid-sleep.
export const EPOCH_S = 1699981200;
// The night, in the PC's local time: things that move "over the night" (the moon, the
// zoom) go from one end to the other between these hours, and hold still outside them.
const NIGHT_START_H = 22;
const NIGHT_HOURS = 10;
const NOON_H = 12;

/**
 * Sky time now, in seconds.
 */
export function skyTime() {
  return Date.now() / 1000 - EPOCH_S;
}

/**
 * A slow wave in [0, 1] for anything that pulses: 0 at its brightest, 1 at its dimmest.
 * `cycle` is {period, phase} in seconds and radians.
 */
export function swell(t, { period, phase }) {
  return 0.5 + 0.5 * Math.sin((2 * Math.PI * t) / period + phase);
}

/**
 * Smoothstep: 0 at or below 0, 1 at or above 1, an S-curve between.
 */
export function ease(u) {
  const x = Math.min(1, Math.max(0, u));
  return x * x * (3 - 2 * x);
}

/**
 * A fade in [0, 1]: 0 before `start`, rising over `rise` seconds, holding `hold`, falling
 * over `fall`, 0 after. The ramps are eased, so nothing ever jumps.
 */
export function envelope(t, start, { rise, hold, fall }) {
  const elapsed = t - start;
  const total = rise + hold + fall;
  if (elapsed <= 0 || elapsed >= total) return 0;
  if (elapsed < rise) return ease(elapsed / rise);
  if (elapsed < rise + hold) return 1;
  return ease((total - elapsed) / fall);
}

/**
 * Where `t` falls in a repeating cycle of `period` seconds: {index, local}, the cycle's
 * number since sky time zero and the seconds into it.
 */
export function cycleAt(t, period) {
  const index = Math.floor(t / period);
  return { index, local: t - index * period };
}

/**
 * The event of a repeating schedule in progress at `t`, or null. `schedule` is {period,
 * seed} (seconds, and an integer from random.js's childSeed); each cycle's event runs
 * for `duration` seconds from the cycle's start. Returns {local, next}: seconds into the
 * event and a generator for its details, the same one every time that event is asked.
 */
export function eventAt(t, schedule, duration) {
  const { index, local } = cycleAt(t, schedule.period);
  if (local >= duration) return null;
  return { local, next: eventRandom(schedule.seed, index) };
}

/**
 * How far through the night sky time `t` is, in [0, 1], by the PC's local clock (the
 * zone and its daylight saving come from Date): 0 until 22:00, 1 from 08:00, and held at
 * those ends through the evening and the morning.
 */
export function nightProgress(t) {
  const local = new Date((t + EPOCH_S) * 1000);
  const hours = local.getHours() + local.getMinutes() / 60 + local.getSeconds() / 3600;
  // Hours since 22:00: negative through the evening, past the window by late morning.
  const since = hours >= NOON_H ? hours - NIGHT_START_H : hours + (24 - NIGHT_START_H);
  return Math.min(1, Math.max(0, since / NIGHT_HOURS));
}
