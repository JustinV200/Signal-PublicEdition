// The status line's connection words: server down, never claimed and a closed
// session each read differently and never say "Connected"; the turn states sit
// behind `Claude · `; the tooltip starts with the full text, then the session and its claim age.
import { describe, expect, it } from "vitest";
import type { CheckLevel, TurnStatus } from "../../src/api";
import { initialState } from "../../src/state";
import type { AppState } from "../../src/state";
import { connectionWords } from "../../src/status";
import { serverState } from "../state/serverFixture";

const NOW = Date.parse("2026-11-17T12:00:00Z");
const MS_PER_MINUTE = 60_000;
const ONLINE = { ...initialState, connection: { status: "online" } } as const;

/** Online, with the fixture's session as `claimed` / `alive` and its turn changed by `turn`. */
function online(
  orchestrator: { claimed: boolean; alive: boolean; claimedAt?: string },
  turn?: Partial<TurnStatus>,
): AppState {
  const server = serverState();
  server.orchestrator = {
    ...server.orchestrator,
    ...orchestrator,
    turn: { ...server.orchestrator.turn, ...turn },
  };
  return { ...ONLINE, server };
}

const LINKED = { claimed: true, alive: true };
/** The console's health with the turn hook check at `level`. */
const turnHook = (level: CheckLevel) => ({
  checks: [
    { id: "turn-hook", name: "Turn hook", level, state: "", words: "", fix: "", command: "" },
  ],
  error: null,
  loading: false,
});

describe("connectionWords", () => {
  it.each<[string, AppState, string, boolean]>([
    [
      "server down",
      { ...initialState, connection: { status: "offline", retryAt: NOW + 3000, since: NOW } },
      "Console server not answering · retrying in 3s",
      true,
    ],
    ["before the first snapshot", ONLINE, "Connecting…", false],
    [
      "never claimed",
      online({ claimed: false, alive: false }),
      'No Claude session · run "console claim" in Claude Code',
      true,
    ],
    [
      "claimed, session closed",
      online({ claimed: true, alive: false }),
      "Claude session closed",
      true,
    ],
    ["idle", online(LINKED), "Claude · idle", false],
    [
      "working with agents",
      online(LINKED, { state: "working", startedAt: NOW - 42_000, agents: 5 }),
      "Claude · working 0:42 · 5 agents",
      false,
    ],
    [
      "quiet",
      online(LINKED, { state: "stale", lastActivityAt: NOW - 12 * MS_PER_MINUTE }),
      "Claude · quiet for 12 min (interrupted?)",
      true,
    ],
    [
      "no hook yet",
      { ...online(LINKED, { state: "unknown" }), health: turnHook("ok") },
      "Claude · state unknown until its next turn",
      false,
    ],
    [
      "turn hook missing",
      { ...online(LINKED, { state: "unknown" }), health: turnHook("fail") },
      "Claude · state unknown · turn hook missing",
      true,
    ],
  ])("%s", (_case, state, text, warn) => {
    const words = connectionWords(state, NOW);
    expect(words.parts.join(" · ")).toBe(text);
    expect(words.title.split("\n")[0]).toBe(text);
    expect(words.warn).toBe(warn);
    // The live region's words hold no clock: a second later they are the same.
    expect(connectionWords(state, NOW + 1000).spoken).toBe(words.spoken);
  });

  it("names the session and how long ago it linked, never a raw time", () => {
    const tooltipSession = (claimedAt: string) =>
      connectionWords(online({ ...LINKED, claimedAt }), NOW).title.split("\n")[1];
    expect(tooltipSession("2026-10-22T12:00:00+00:00")).toBe("Session: main, linked 26d ago");
    expect(tooltipSession("not a time")).toBe("Session: main");
  });
});
