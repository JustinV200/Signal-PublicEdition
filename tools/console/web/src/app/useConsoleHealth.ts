// Reads the console's own checks (GET /api/health) into the store: once at
// sign-in (the status line's pointer and the `state unknown` cause need them),
// again each time System opens, on the Refresh button and on System's Check
// again. Never on a timer: each read scans the process table on the server.
// A failed read keeps the last rows and says why; a 401 signs the page out.
import { useEffect, useState } from "react";
import { getHealth, UnauthorizedError } from "../api";
import { useStore } from "../state";

/**
 * Keeps `state.health` filled. Mounted once, by the shell.
 *
 * @param isSystemOpen System is the current view; each opening reads again (leaving does not).
 */
export function useConsoleHealth(isSystemOpen: boolean): void {
  const { state, dispatch } = useStore();
  const { refreshTick, healthTick } = state;
  // Counts System's openings, set during render (React's "adjust state when props change").
  const [wasOpen, setWasOpen] = useState(isSystemOpen);
  const [openings, setOpenings] = useState(0);
  if (wasOpen !== isSystemOpen) {
    setWasOpen(isSystemOpen);
    if (isSystemOpen) setOpenings((count) => count + 1);
  }

  useEffect(() => {
    let cancelled = false;
    // The last rows stay while the next read runs, so nothing on the page blinks.
    const last = state.health;
    dispatch({ type: "health", health: { ...last, loading: true } });
    getHealth()
      .then((checks) => {
        if (!cancelled)
          dispatch({ type: "health", health: { checks, error: null, loading: false } });
      })
      .catch((failure: unknown) => {
        if (cancelled) return;
        if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
        const error = failure instanceof Error ? failure.message : String(failure);
        dispatch({ type: "health", health: { ...last, error, loading: false } });
      });
    return () => {
      cancelled = true;
    };
    // state.health is read for the rows to keep, not as a reason to read again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openings, refreshTick, healthTick, dispatch]);
}
