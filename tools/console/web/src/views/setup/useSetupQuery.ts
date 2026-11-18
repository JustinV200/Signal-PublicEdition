// Reads one setup CLI answer (a read-only command such as `list`, `intro`,
// `plan`, `tour` or `status`) when a view opens, parses it, and re-reads on
// reload() or the status line's Refresh. Shared by the wizard's screens,
// System's tools list and the Setup tab rule (useSetupTab).
import { useCallback, useEffect, useState } from "react";
import { runSetup, UnauthorizedError } from "../../api";
import type { SetupRequest } from "../../api";
import { useStore } from "../../state";

export interface SetupQuery<T> {
  /** The parsed answer; null before the first one arrives. */
  data: T | null;
  /** Why the last read failed; null when it worked. */
  error: string | null;
  loading: boolean;
  /** Reads again now. */
  reload: () => void;
}

/**
 * Runs `request` and keeps `parse(lines, exit)` of its output. `key` must change
 * when `request` does (requests are objects, so they can't be the dependency).
 */
export function useSetupQuery<T>(
  key: string,
  request: SetupRequest,
  parse: (lines: string[], exit: number) => T,
): SetupQuery<T> {
  const { state, dispatch } = useStore();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  // Which read the current data answers; loading until it matches the one asked for.
  const readKey = `${key}:${tick}:${state.refreshTick}`;
  const [answered, setAnswered] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    runSetup(request)
      .then((result) => {
        if (cancelled) return;
        setData(parse(result.lines, result.exit));
        setError(null);
      })
      .catch((failure: unknown) => {
        if (cancelled) return;
        if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
        setError(failure instanceof Error ? failure.message : String(failure));
      })
      .finally(() => {
        if (!cancelled) setAnswered(readKey);
      });
    return () => {
      cancelled = true;
    };
    // readKey stands for request and parse (via key), and changes on reload and Refresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readKey, dispatch]);

  const reload = useCallback(() => setTick((old) => old + 1), []);
  return { data, error, loading: answered !== readKey, reload };
}
