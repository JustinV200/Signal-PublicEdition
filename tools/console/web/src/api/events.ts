// The event stream: GET /api/events read with streaming fetch (EventSource
// cannot send the token header), parsed by sse.ts. On any drop we wait
// 1/2/4/8 s, re-fetch /api/state (which also surfaces a 401) and reopen.
//
// A stream can also go quiet without dropping: a window Edge froze or put to
// sleep, or a socket left half-open after the laptop slept. The server writes
// a keepalive every few seconds, so a stream with no bytes for STALL_MS counts
// as dead and is reopened. `resync()` reopens at once (the Refresh button and
// the page becoming visible again).
import { getState, rejectUnauthorized, UnauthorizedError } from "./client";
import { parseServerEvent } from "./parse";
import { createSseParser } from "./sse";
import { authHeaders } from "./token";
import type { ServerEvent } from "./types";

const EVENTS_PATH = "/api/events";
const BACKOFF_SECONDS = [1, 2, 4, 8];
const MS_PER_SECOND = 1000;
/** No byte for this long means a dead stream. The server's keepalive is every 5 s (15 s before). */
export const STALL_MS = 20_000;

/**
 * True past STALL_MS since the server's last byte (`syncedAt`, epoch ms), or before the first
 * one. The status line's `no update for 25s` and the scope's `NO SIGNAL 25s` both use it.
 */
export function isStreamStale(syncedAt: number | null, now: number): boolean {
  return syncedAt === null || now - syncedAt > STALL_MS;
}

export interface EventHandlers {
  onEvent: (event: ServerEvent) => void;
  /** The stream is open (also fires after each reconnect). */
  onOnline: () => void;
  /** The stream dropped; a reconnect is due in `retryInSeconds`. */
  onOffline: (retryInSeconds: number) => void;
  /** The token is gone; the loop stops until `connectEvents` is called again. */
  onUnauthorized: () => void;
  /** Bytes arrived (an event or a keepalive): what the page shows is current as of now. */
  onAlive: () => void;
}

export interface EventStream {
  /** Drops the current stream and reconnects now: a fresh /api/state, then the stream. */
  resync: () => void;
  /** Closes the stream and cancels any pending reconnect. */
  close: () => void;
}

function dispatchEvent(name: string, raw: string, onEvent: EventHandlers["onEvent"]): void {
  try {
    const event = parseServerEvent(name, raw);
    if (event) onEvent(event);
  } catch (error) {
    // One malformed event must not kill the stream; log it and move on.
    console.error(`bad ${name} event`, error);
  }
}

/** A timer that aborts `controller` unless `kick()` is called within `ms`. */
function stallWatchdog(controller: AbortController, ms: number) {
  let timer = setTimeout(() => controller.abort(), ms);
  return {
    kick: () => {
      clearTimeout(timer);
      timer = setTimeout(() => controller.abort(), ms);
    },
    stop: () => clearTimeout(timer),
  };
}

/** Reads the stream until the server closes it, it stalls, or `controller` aborts. */
async function readStream(handlers: EventHandlers, controller: AbortController): Promise<void> {
  // Armed before the fetch too: a request stuck pending is as dead as a quiet stream.
  const watchdog = stallWatchdog(controller, STALL_MS);
  try {
    const response = await fetch(EVENTS_PATH, {
      headers: authHeaders(),
      credentials: "same-origin",
      signal: controller.signal,
    });
    rejectUnauthorized(response);
    if (!response.ok || !response.body) throw new Error(`${EVENTS_PATH}: HTTP ${response.status}`);
    handlers.onOnline();
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    const parser = createSseParser();
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return;
      watchdog.kick();
      handlers.onAlive();
      for (const { event, data } of parser.feed(value))
        dispatchEvent(event, data, handlers.onEvent);
    }
  } finally {
    watchdog.stop();
  }
}

/** Opens the event stream and keeps it open, reconnecting after drops and stalls. */
export function connectEvents(handlers: EventHandlers): EventStream {
  let timer: ReturnType<typeof setTimeout> | null = null;
  let current: AbortController | null = null;
  let attempt = 0;
  // Bumped by resync and close: a stream from an older generation never reconnects.
  let generation = 0;
  let closed = false;

  const scheduleReconnect = () => {
    const seconds = BACKOFF_SECONDS[Math.min(attempt, BACKOFF_SECONDS.length - 1)];
    attempt += 1;
    handlers.onOffline(seconds);
    const gen = generation;
    timer = setTimeout(() => void probeThenRun(gen), seconds * MS_PER_SECOND);
  };

  const run = async (gen: number) => {
    const controller = new AbortController();
    current = controller;
    const onOnline = () => {
      attempt = 0;
      handlers.onOnline();
    };
    try {
      await readStream({ ...handlers, onOnline }, controller);
      // The server ended the stream cleanly (restart or idle timeout): reconnect.
      if (gen === generation) scheduleReconnect();
    } catch (error) {
      if (closed || gen !== generation) return;
      if (error instanceof UnauthorizedError) handlers.onUnauthorized();
      else scheduleReconnect(); // a drop, or the watchdog's abort after a stall
    }
  };

  // Reconnect through /api/state so a dead token is noticed and the UI gets a
  // fresh snapshot before the replay.
  const probeThenRun = async (gen: number) => {
    try {
      const data = await getState();
      if (gen !== generation) return;
      handlers.onEvent({ type: "state", data });
    } catch (error) {
      if (gen !== generation) return;
      if (error instanceof UnauthorizedError) handlers.onUnauthorized();
      else scheduleReconnect();
      return;
    }
    void run(gen);
  };

  // Ends the current stream and any pending reconnect without starting another.
  const stop = () => {
    generation += 1;
    if (timer) clearTimeout(timer);
    timer = null;
    current?.abort();
    current = null;
  };

  void run(generation);

  return {
    resync: () => {
      if (closed) return;
      stop();
      attempt = 0;
      void probeThenRun(generation);
    },
    close: () => {
      closed = true;
      stop();
    },
  };
}
