// The console tour's stops and where it resumes. Chat comes first (how to
// talk to Claude and link it), then Tasks, System and Scope, then only the
// tabs of the tools that were picked (Voice is audiohub's, Boards the
// whiteboard's). While the picks are unknown (not read yet, or `setup list`
// failed) every tool tab stays in. The last stop is kept in localStorage, so
// `Take the tour` resumes where the owner left it; Finish forgets it.
import type { View } from "../types";

const CORE_STOPS: readonly View[] = ["chat", "tasks", "system", "scope"];
/** Each tool tab and the registry tool it belongs to. */
const TOOL_STOPS: ReadonlyArray<readonly [View, string]> = [
  ["voice", "audiohub"],
  ["boards", "whiteboard"],
];
const STORAGE_KEY = "signal-console-tour-stop";

/**
 * The tour's stops in order.
 *
 * @param picks The picked tool ids; null while unknown.
 * @returns The views the tour visits.
 */
export function tourStops(picks: readonly string[] | null): View[] {
  const tools = TOOL_STOPS.filter(([, tool]) => picks === null || picks.includes(tool));
  return [...CORE_STOPS, ...tools.map(([view]) => view)];
}

/** The remembered stop when it is still one of `picks`' stops, else the first stop. */
export function resumeTourStop(picks: readonly string[] | null): View {
  const stops = tourStops(picks);
  let saved: string | null = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the tour starts at its first stop.
  }
  return stops.find((stop) => stop === saved) ?? stops[0];
}

/** Remembers `stop` for the next start; null forgets it (the tour was finished). */
export function saveTourStop(stop: View | null): void {
  try {
    if (stop) localStorage.setItem(STORAGE_KEY, stop);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the tour still runs, it just starts over next time.
  }
}
