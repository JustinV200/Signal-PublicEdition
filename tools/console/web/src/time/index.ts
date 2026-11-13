// Public entry point of the time package.
export {
  formatClock,
  formatClockSeconds,
  formatDayLabel,
  formatElapsed,
  formatRelative,
  isSameDay,
  toMs,
} from "./format";
export type { TimeLike } from "./format";
export { useTicker } from "./useTicker";
