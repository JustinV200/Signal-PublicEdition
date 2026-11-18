// What the radar's distances mean. A task's range is its progress (rim 0%,
// just outside the centre at 100%); everything else's is the time since it
// last did something, read against the rings captioned `now / 1m / 5m`. Also the sectors each
// subsystem owns, and the `NO SIGNAL 25s` words for a stale stream.
import { isStreamStale } from "../../../api";
import { shortAge } from "../../../time";

/** A subsystem's slice of the face, clockwise from `fromDeg` to `toDeg`. */
export interface Sector {
  name: string;
  fromDeg: number;
  toDeg: number;
}

// Voice and the board share the right half (their pending requests sit beside
// them); tasks get the whole left half, since there can be many.
export const SECTORS = {
  voice: { name: "VOICE", fromDeg: 0, toDeg: 90 },
  board: { name: "BOARD", fromDeg: 90, toDeg: 180 },
  tasks: { name: "TASKS", fromDeg: 180, toDeg: 360 },
} satisfies Record<string, Sector>;

const MS_PER_MINUTE = 60_000;
const NOW_RING = 1 / 3;
const MINUTE_RING = 2 / 3;
const FIVE_MINUTE_RING = 1;
const FIVE_MINUTES_MS = 5 * MS_PER_MINUTE;

/** The range rings, each captioned with the age a blip on it has. */
export const RINGS = [
  { fraction: NOW_RING, caption: "now" },
  { fraction: MINUTE_RING, caption: "1m" },
  { fraction: FIVE_MINUTE_RING, caption: "5m" },
];

const MAX_PERCENT = 100;
// 100% stops just outside Claude's mark, so a finished task never covers it.
const MIN_TASK_RANGE = 0.1;

/** A task's range: 1 (the rim) at 0%, linear to MIN_TASK_RANGE (by the centre) at 100%, clamped. */
export function percentRange(pct: number): number {
  const clamped = Math.min(MAX_PERCENT, Math.max(0, pct));
  return MIN_TASK_RANGE + (1 - MIN_TASK_RANGE) * (1 - clamped / MAX_PERCENT);
}

/**
 * The range for something last active `ageMs` ago: on the `now` ring at 0,
 * linear to the `1m` ring, then linear to the `5m` rim, and on the rim when
 * older or never active (null).
 */
export function ageRange(ageMs: number | null): number {
  if (ageMs === null || ageMs >= FIVE_MINUTES_MS) return FIVE_MINUTE_RING;
  const age = Math.max(0, ageMs);
  if (age <= MS_PER_MINUTE) return NOW_RING + (MINUTE_RING - NOW_RING) * (age / MS_PER_MINUTE);
  const pastMinute = (age - MS_PER_MINUTE) / (FIVE_MINUTES_MS - MS_PER_MINUTE);
  return MINUTE_RING + (FIVE_MINUTE_RING - MINUTE_RING) * pastMinute;
}

/**
 * `NO SIGNAL 25s` (the age of the last byte, `syncedAt`) once the stream is stale
 * by the status line's own test or has dropped (`isOffline`), `NO SIGNAL` offline
 * before any byte, or null while bytes arrive and while the first is still due
 * (so it doesn't flash on each load): the sweep runs only then.
 */
export function signalWords(
  syncedAt: number | null,
  isOffline: boolean,
  now: number,
): string | null {
  if (!isOffline && (syncedAt === null || !isStreamStale(syncedAt, now))) return null;
  return syncedAt === null ? "NO SIGNAL" : `NO SIGNAL ${shortAge(Math.max(0, now - syncedAt))}`;
}
