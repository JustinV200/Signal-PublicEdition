// One setup command at a time from a wizard control: runs it through
// POST /api/setup/run, keeps its output lines as they stream in (shown live by
// OutputLog) and its exit code. A 401 signs the page out like every call; a
// refused request (400/409) or a dropped stream becomes `error`.
import { useCallback, useState } from "react";
import { runSetup, UnauthorizedError } from "../../../api";
import type { SetupRequest, SetupResult } from "../../../api";
import { useStore } from "../../../state";

export interface SetupRun {
  /** Output lines so far (this run, or the last one). */
  lines: string[];
  /** The last run's exit code; null while running or before any run. */
  exit: number | null;
  running: boolean;
  /** Why the request itself failed (not a failing step: that is `exit`). */
  error: string | null;
  /** Runs `request`; resolves with its result, or null when the request failed. */
  run: (request: SetupRequest) => Promise<SetupResult | null>;
}

/** A runner for one control's commands (each control keeps its own log). */
export function useSetupRun(): SetupRun {
  const { dispatch } = useStore();
  const [lines, setLines] = useState<string[]>([]);
  const [exit, setExit] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (request: SetupRequest) => {
      setLines([]);
      setExit(null);
      setError(null);
      setRunning(true);
      try {
        const result = await runSetup(request, (line) => setLines((old) => [...old, line]));
        setExit(result.exit);
        return result;
      } catch (failure) {
        if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
        setError(failure instanceof Error ? failure.message : String(failure));
        return null;
      } finally {
        setRunning(false);
      }
    },
    [dispatch],
  );
  return { lines, exit, running, error, run };
}
