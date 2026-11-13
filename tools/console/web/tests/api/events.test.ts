// The event stream must never sit "connected" on a stream that stopped
// delivering (a frozen window, a socket left half-open after sleep): a quiet
// stream is reopened after STALL_MS, and resync() reopens one at once.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { connectEvents, STALL_MS } from "../../src/api";
import type { EventHandlers } from "../../src/api";

const STATE = {
  orchestrator: {
    claimed: true,
    label: "main",
    turn: { state: "idle", startedAt: null, lastActivityAt: null, agents: 0, agentsUnsure: false },
  },
  voice: { running: false, phase: null, startedBy: null },
  board: { saves: [], view: null, online: false },
  models: null,
};
const FIRST_BACKOFF_MS = 1000;

/** An SSE body that sends one state event, then stays open and silent until aborted. */
function quietStream(signal: AbortSignal): Response {
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(
        new TextEncoder().encode(`event: state\ndata: ${JSON.stringify(STATE)}\n\n`),
      );
      signal.addEventListener("abort", () =>
        controller.error(new DOMException("aborted", "AbortError")),
      );
    },
  });
  return new Response(body, { status: 200 });
}

function fakeServer() {
  const fetchMock = vi.fn((url: string, init: RequestInit) =>
    Promise.resolve(
      url === "/api/events"
        ? quietStream(init.signal as AbortSignal)
        : new Response(JSON.stringify(STATE), { status: 200 }),
    ),
  );
  vi.stubGlobal("fetch", fetchMock);
  const calls = (path: string) => fetchMock.mock.calls.filter(([url]) => url === path).length;
  return { calls };
}

function handlers(): EventHandlers {
  return {
    onEvent: vi.fn(),
    onOnline: vi.fn(),
    onOffline: vi.fn(),
    onUnauthorized: vi.fn(),
    onAlive: vi.fn(),
  };
}

// Lets the fake fetch, the stream pipes and the reconnect chain run.
const settle = () => vi.advanceTimersByTimeAsync(0);

beforeEach(() => vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }));
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("connectEvents", () => {
  it("reopens a stream that sends nothing for STALL_MS", async () => {
    const server = fakeServer();
    const on = handlers();
    const stream = connectEvents(on);
    await settle();
    expect(on.onAlive).toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(STALL_MS - 1);
    expect(server.calls("/api/events")).toBe(1); // still trusted just before the limit

    await vi.advanceTimersByTimeAsync(1 + FIRST_BACKOFF_MS);
    expect(on.onOffline).toHaveBeenCalledWith(1);
    expect(server.calls("/api/state")).toBe(1); // a fresh snapshot before the reopen
    expect(server.calls("/api/events")).toBe(2);
    stream.close();
  });

  it("resync reopens at once with a fresh snapshot, without reading as offline", async () => {
    const server = fakeServer();
    const on = handlers();
    const stream = connectEvents(on);
    await settle();

    stream.resync();
    await settle();
    expect(server.calls("/api/state")).toBe(1);
    expect(server.calls("/api/events")).toBe(2);
    expect(on.onOffline).not.toHaveBeenCalled(); // the aborted old stream never schedules a retry
    stream.close();
  });
});
