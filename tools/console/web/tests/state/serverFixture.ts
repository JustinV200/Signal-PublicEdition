// A server snapshot for the state tests: an idle claimed session, voice off,
// and the board fields a test gives (saves by name, view, online, item count).
import type { BoardState, ServerState } from "../../src/api";

/** A snapshot whose board is `board` over an online, empty whiteboard. */
export function serverState(board: Partial<BoardState> = {}): ServerState {
  return {
    orchestrator: {
      claimed: true,
      alive: true,
      label: "main",
      claimedAt: null,
      turn: {
        state: "idle",
        startedAt: null,
        lastActivityAt: null,
        agents: 0,
        agentsUnsure: false,
      },
    },
    voice: { running: false, phase: null, startedBy: null },
    board: { saves: [], view: "items", itemCount: null, online: true, ...board },
    models: null,
    away: null,
    openCommand: null,
  };
}

/** Saves with just names, in server order. */
export function savesNamed(...names: string[]): BoardState["saves"] {
  return names.map((name) => ({ name, updatedAt: null, description: null, refresher: null }));
}
