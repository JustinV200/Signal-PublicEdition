// Polls GET /api/devices while the Devices view is open and the page is
// visible, and re-reads at once on the Refresh button: a read like the status line's, so it never reaches Claude. A 401
// signs the page out like every other call.
import { useCallback, useEffect, useState } from "react";
import { getDevices, UnauthorizedError } from "../../api";
import type { AwayInfo, DevicesPayload } from "../../api";
import { useStore } from "../../state";
import { usePageVisible } from "../../ui";

const POLL_MS = 5000;

export interface DevicesState {
  /** The last good answer; null before the first. */
  payload: DevicesPayload | null;
  /** Why the last read failed, in words; null when it worked. */
  error: string | null;
  /** Epoch ms of the last good read; null before the first. */
  readAt: number | null;
  /** Puts a fresh away block in (after the toggle) without waiting for the next poll. */
  setAway: (away: AwayInfo) => void;
}

/** The device rows and away mode, refreshed every POLL_MS. */
export function useDevices(): DevicesState {
  const { state, dispatch } = useStore();
  const { refreshTick } = state;
  const visible = usePageVisible();
  const [payload, setPayload] = useState<DevicesPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [readAt, setReadAt] = useState<number | null>(null);

  useEffect(() => {
    if (!visible) return;
    let cancelled = false;
    const read = async () => {
      try {
        const next = await getDevices();
        if (cancelled) return;
        setPayload(next);
        setReadAt(Date.now());
        setError(null);
      } catch (failure) {
        if (cancelled) return;
        if (failure instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
        setError(failure instanceof Error ? failure.message : String(failure));
      }
    };
    void read();
    const timer = setInterval(() => void read(), POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
    // refreshTick is not read inside: a change just restarts the poll with a read now.
  }, [visible, dispatch, refreshTick]);

  const setAway = useCallback(
    (away: AwayInfo) => setPayload((old) => (old ? { ...old, away } : old)),
    [],
  );
  return { payload, error, readAt, setAway };
}
