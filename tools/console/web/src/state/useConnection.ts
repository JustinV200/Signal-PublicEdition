// Drives the session lifecycle from the store's `auth` field:
//   checking -> startSession -> in | out
//   in       -> event stream connected (its probe turns a dead token into out);
//               it resyncs on the Refresh button, when the page becomes
//               visible again and when the network comes back
//   out      -> wait for hashchange (a new key) or window focus, then checking
import { useEffect, useRef } from "react";
import type { Dispatch } from "react";
import { connectEvents, getState, login } from "../api";
import type { EventStream } from "../api";
import type { Auth, StoreAction } from "./reducer";
import { startSession, takeHashKey } from "./session";

const MS_PER_SECOND = 1000;

type KeyRef = { current: string | null };

function useSessionStart(auth: Auth, dispatch: Dispatch<StoreAction>, keyRef: KeyRef): void {
  useEffect(() => {
    if (auth !== "checking") return;
    let cancelled = false;
    // A key is one-shot: hand it over and forget it so a retry does not reuse it.
    const key = keyRef.current;
    keyRef.current = null;
    void startSession(key, { login, getState }).then((outcome) => {
      if (cancelled) return;
      if (outcome.kind === "in") {
        dispatch({
          type: "server",
          event: { type: "state", data: outcome.state },
          now: Date.now(),
        });
      }
      if (outcome.kind === "down") console.error("console backend unreachable", outcome.error);
      // `down` still opens the shell: the stream's backoff shows `offline` and keeps retrying.
      dispatch({ type: "auth", auth: outcome.kind === "out" ? "out" : "in" });
    });
    return () => {
      cancelled = true;
    };
  }, [auth, dispatch, keyRef]);
}

function useEventStream(auth: Auth, dispatch: Dispatch<StoreAction>, refreshTick: number): void {
  const streamRef = useRef<EventStream | null>(null);
  useEffect(() => {
    if (auth !== "in") return;
    const stream = connectEvents({
      onEvent: (event) => dispatch({ type: "server", event, now: Date.now() }),
      onOnline: () => dispatch({ type: "connection", connection: { status: "online" } }),
      onOffline: (retryInSeconds) =>
        dispatch({
          type: "connection",
          connection: { status: "offline", retryAt: Date.now() + retryInSeconds * MS_PER_SECOND },
        }),
      onUnauthorized: () => dispatch({ type: "auth", auth: "out" }),
      onAlive: () => dispatch({ type: "alive", at: Date.now() }),
    });
    streamRef.current = stream;
    // A hidden or sleeping window may have missed updates or hold a dead
    // socket; coming back (or the network returning) re-reads everything.
    const resyncIfVisible = () => {
      if (document.visibilityState === "visible") stream.resync();
    };
    document.addEventListener("visibilitychange", resyncIfVisible);
    window.addEventListener("online", resyncIfVisible);
    return () => {
      document.removeEventListener("visibilitychange", resyncIfVisible);
      window.removeEventListener("online", resyncIfVisible);
      stream.close();
      streamRef.current = null;
    };
  }, [auth, dispatch]);

  // The Refresh button: tick 0 is the initial render, not a click.
  useEffect(() => {
    if (refreshTick > 0) streamRef.current?.resync();
  }, [refreshTick]);
}

function useSignedOutRetry(auth: Auth, dispatch: Dispatch<StoreAction>, keyRef: KeyRef): void {
  useEffect(() => {
    if (auth !== "out") return;
    const retry = () => dispatch({ type: "auth", auth: "checking" });
    const onHashChange = () => {
      keyRef.current = takeHashKey();
      retry();
    };
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("focus", retry);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
      window.removeEventListener("focus", retry);
    };
  }, [auth, dispatch, keyRef]);
}

/**
 * Mounts the whole login / stream / retry lifecycle. Call once, in the store
 * provider, with the key taken from the URL before the first render and the
 * store's `refreshTick` (a change re-reads everything now).
 */
export function useConnection(
  auth: Auth,
  dispatch: Dispatch<StoreAction>,
  loginKey: string | null,
  refreshTick: number,
): void {
  const keyRef = useRef(loginKey);
  useSessionStart(auth, dispatch, keyRef);
  useEventStream(auth, dispatch, refreshTick);
  useSignedOutRetry(auth, dispatch, keyRef);
}
