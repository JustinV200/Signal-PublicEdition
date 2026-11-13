// A React hook that re-renders on an interval and returns the current time,
// for the working stopwatch, the offline countdown and relative ages.
import { useEffect, useState } from "react";

/** Returns `Date.now()` refreshed every `intervalMs` (at most one interval stale). */
export function useTicker(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(timer);
  }, [intervalMs]);
  return now;
}
