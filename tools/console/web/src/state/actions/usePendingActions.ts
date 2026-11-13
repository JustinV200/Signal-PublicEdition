// Binds `pendingActions` to the store for the views' buttons: which action
// names are still on their way, refreshed every few seconds so the time cap
// can lift a wedged one.
import { useMemo } from "react";
import type { ActionName } from "../../api";
import { useTicker } from "../../time";
import { useStore } from "../store";
import { pendingActions } from "./actionProgress";

// Only the PENDING_MAX_MS cap depends on the clock, so a coarse tick is enough.
const TICK_MS = 5000;

/** The set of actions with a request still on its way. */
export function usePendingActions(): Set<ActionName> {
  const { state } = useStore();
  const now = useTicker(TICK_MS);
  return useMemo(() => pendingActions(state.messages, now), [state.messages, now]);
}
