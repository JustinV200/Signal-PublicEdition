// React context for the console state: one reducer, one dispatch, one sender.
// `StoreProvider` also mounts the connection lifecycle.
import { createContext, useContext, useMemo, useReducer } from "react";
import type { Dispatch, ReactNode } from "react";
// Straight from sending.ts, not actions/index.ts: that index also exports
// usePendingActions, which imports this store (a cycle).
import { createSender } from "./actions/sending";
import type { Sender } from "./actions/sending";
import { reduce, startState } from "./reducer";
import type { AppState, StoreAction } from "./reducer";
import { useConnection } from "./useConnection";

interface StoreValue {
  state: AppState;
  dispatch: Dispatch<StoreAction>;
  sender: Sender;
}

const StoreContext = createContext<StoreValue | null>(null);

interface StoreProviderProps {
  /** The `#k=` key taken from the URL before the first render, if any. */
  loginKey: string | null;
  /** The view (and, for the setup wizard, the tool) the opening URL asked for. */
  startView?: string | null;
  startTool?: string | null;
  children: ReactNode;
}

/** Provides the store to the tree and starts the session. */
export function StoreProvider({
  loginKey,
  startView = null,
  startTool = null,
  children,
}: StoreProviderProps) {
  const [state, dispatch] = useReducer(reduce, null, () => startState(startView, startTool));
  const sender = useMemo(() => createSender(dispatch), [dispatch]);
  useConnection(state.auth, dispatch, loginKey, state.refreshTick);
  const value = useMemo(() => ({ state, dispatch, sender }), [state, dispatch, sender]);
  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

/** The store; throws outside a `StoreProvider`. */
export function useStore(): StoreValue {
  const value = useContext(StoreContext);
  if (!value) throw new Error("useStore outside StoreProvider");
  return value;
}
