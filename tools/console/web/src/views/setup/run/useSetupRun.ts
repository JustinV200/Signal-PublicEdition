// One setup command at a time from a wizard control: runs it through
// POST /api/setup/run, keeps its output lines as they stream in (shown live by
// OutputLog) and its exit code. A 401 signs the page out like every call; a
// refused request (400) or a dropped stream becomes `error`, and a 409 (another
// command is running) becomes `error` with `busy` set, which is no failure.
// The wizard's runners share one running state (runningState.tsx): `button`
// gives each of a control's buttons its look, so only the clicked one reads
// "Working…".
import { useCallback, useId, useState } from "react";
import { runSetup, SetupBusyError, UnauthorizedError } from "../../../api";
import type { SetupRequest, SetupResult } from "../../../api";
import { useStore } from "../../../state";
import { buttonLook, claim, release, useRunningState } from "./runningState";
import type { ButtonLook } from "./runningState";

/** The key of a control's only (or main) button. */
const MAIN_BUTTON = "main";

export interface SetupRun {
  /** Output lines so far (this run, or the last one). */
  lines: string[];
  /** The last run's exit code; null while running or before any run. */
  exit: number | null;
  running: boolean;
  /** Why the request itself failed (not a failing step: that is `exit`). */
  error: string | null;
  /** The request was refused because another command is running (a 409): nothing failed. */
  busy: boolean;
  /**
   * Runs `request` for the button keyed `button` (default: the main one);
   * resolves with its result, or null when the request failed.
   */
  run: (request: SetupRequest, button?: string) => Promise<SetupResult | null>;
  /** The look of this control's button keyed `button` (default: the main one). */
  button: (button?: string) => ButtonLook;
}

/** A runner for one control's commands (each control keeps its own log). */
export function useSetupRun(): SetupRun {
  const { dispatch } = useStore();
  const id = useId();
  const { active, setActive } = useRunningState();
  const [lines, setLines] = useState<string[]>([]);
  const [exit, setExit] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const run = useCallback(
    async (request: SetupRequest, button = MAIN_BUTTON) => {
      const key = `${id}:${button}`;
      setActive((old) => claim(old, key));
      setLines([]);
      setExit(null);
      setError(null);
      setBusy(false);
      setRunning(true);
      try {
        const result = await runSetup(request, (line) => setLines((old) => [...old, line]));
        setExit(result.exit);
        return result;
      } catch (failure) {
        if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
        setBusy(failure instanceof SetupBusyError);
        setError(failure instanceof Error ? failure.message : String(failure));
        return null;
      } finally {
        setRunning(false);
        setActive((old) => release(old, key));
      }
    },
    [dispatch, id, setActive],
  );
  const button = (key = MAIN_BUTTON) => buttonLook(active, `${id}:${key}`);
  return { lines, exit, running, error, busy, run, button };
}
