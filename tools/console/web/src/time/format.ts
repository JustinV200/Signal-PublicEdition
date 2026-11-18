// Time formatting for the console: clocks, relative ages, the working
// stopwatch and day labels. All functions take a `now` where they depend on
// it, so they stay pure and testable.

const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;
const MINUTES_PER_HOUR = 60;
const HOURS_PER_DAY = 24;
const MS_PER_MINUTE = MS_PER_SECOND * SECONDS_PER_MINUTE;
const MS_PER_HOUR = MS_PER_MINUTE * MINUTES_PER_HOUR;
const MS_PER_DAY = MS_PER_HOUR * HOURS_PER_DAY;

/** A server timestamp: ISO string or epoch milliseconds. */
export type TimeLike = string | number;

/** Epoch milliseconds for a server timestamp; 0 if it cannot be parsed. */
export function toMs(at: TimeLike): number {
  const ms = typeof at === "number" ? at : Date.parse(at);
  return Number.isFinite(ms) ? ms : 0;
}

const pad2 = (n: number) => String(n).padStart(2, "0");

/** Local `HH:MM`. */
export function formatClock(at: TimeLike): string {
  const d = new Date(toMs(at));
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** Local `HH:MM:SS`. */
export function formatClockSeconds(at: TimeLike): string {
  const d = new Date(toMs(at));
  return `${formatClock(at)}:${pad2(d.getSeconds())}`;
}

/** Stopwatch `m:ss` for a duration in milliseconds. */
export function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / MS_PER_SECOND));
  const minutes = Math.floor(totalSeconds / SECONDS_PER_MINUTE);
  return `${minutes}:${pad2(totalSeconds % SECONDS_PER_MINUTE)}`;
}

/** True when both timestamps fall on the same local calendar day. */
export function isSameDay(a: TimeLike, b: TimeLike): boolean {
  const da = new Date(toMs(a));
  const db = new Date(toMs(b));
  return (
    da.getFullYear() === db.getFullYear() &&
    da.getMonth() === db.getMonth() &&
    da.getDate() === db.getDate()
  );
}

/** A compact age: `25s`, `12m`, `3h`. */
export function shortAge(ms: number): string {
  const seconds = Math.floor(ms / MS_PER_SECOND);
  if (seconds < SECONDS_PER_MINUTE) return `${seconds}s`;
  const minutes = Math.floor(seconds / SECONDS_PER_MINUTE);
  if (minutes < MINUTES_PER_HOUR) return `${minutes}m`;
  return `${Math.floor(minutes / MINUTES_PER_HOUR)}h`;
}

/** Short age like `just now`, `5m ago`, `2h ago`, `yesterday`, `3d ago`. */
export function formatRelative(at: TimeLike, now: number): string {
  const age = now - toMs(at);
  if (age < MS_PER_MINUTE) return "just now";
  if (age < MS_PER_HOUR) return `${Math.floor(age / MS_PER_MINUTE)}m ago`;
  if (age < MS_PER_DAY) return `${Math.floor(age / MS_PER_HOUR)}h ago`;
  const days = Math.floor(age / MS_PER_DAY);
  return days === 1 ? "yesterday" : `${days}d ago`;
}

/** Day divider text: `today`, `yesterday`, or a short date like `Mon 13 Oct`. */
export function formatDayLabel(at: TimeLike, now: number): string {
  if (isSameDay(at, now)) return "today";
  if (isSameDay(at, now - MS_PER_DAY)) return "yesterday";
  return new Date(toMs(at)).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}
