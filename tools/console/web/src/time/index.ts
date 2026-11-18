// Public entry point of the time package.
export {
  formatClock,
  formatClockSeconds,
  formatDayLabel,
  formatElapsed,
  formatRelative,
  isSameDay,
  shortAge,
  toMs,
} from "./format";
export type { TimeLike } from "./format";
export { useTicker } from "./useTicker";
