// The mock backend's starting /api/state: the Claude session (mock-seed.mjs),
// Voice, the whiteboard and its saves, the models block, away and the open command,
// shaped by mock-server.mjs's flags. Split out of mock-server.mjs, which
// keeps the live copy and changes it as buttons run.
import { MODELS } from "./mock-models.mjs";
import { awayBlock } from "./mock-pages.mjs";
import { startOrchestrator } from "./mock-seed.mjs";
import { OPEN_COMMAND } from "./session/mock-session.mjs";

const MS = { hour: 3_600_000, day: 86_400_000 };
const ago = (ms) => new Date(Date.now() - ms).toISOString();

// The whiteboard's saves. The real console reads them from the daemon, so an
// off whiteboard lists none; its view is `items` or `todo`, never a save name.
export const SAVES = [
  {
    name: "lecture",
    updatedAt: ago(2 * MS.hour),
    description: "Week 7 lecture notes and the worked example.",
  },
  {
    name: "agent-task-grid",
    updatedAt: ago(MS.day),
    description: "Grid of the agents' tasks and their status, one cell each.",
    refresher: "tasks",
  },
  { name: "stats-notes", updatedAt: ago(3 * MS.day), description: null },
  { name: "club-demo", updatedAt: null, description: "Demo flow for the club meeting." },
];
// Items on the board while a drawing or a loaded save is up (the daemon's `item_count`).
export const BOARD_ITEMS = 4;
// `--many-saves` adds this many plain saves, so the list outgrows the view.
const EXTRA_SAVES = 24;

/**
 * The whiteboard's saves for this run.
 * @param {boolean} manySaves `--many-saves`: SAVES plus EXTRA_SAVES plain made-up ones.
 * @returns {object[]} The saves, newest first.
 */
export function mockSaves(manySaves) {
  if (!manySaves) return SAVES;
  const extra = Array.from({ length: EXTRA_SAVES }, (_, i) => ({
    name: `sketch-${i + 1}`,
    updatedAt: ago((i + 4) * MS.day),
    description: null,
  }));
  return [...SAVES, ...extra];
}

/**
 * The state the mock starts with.
 *
 * @param {{claude?: string, away?: string, whiteboardOff: boolean, oldWhiteboard: boolean,
 *   emptyBoard: boolean, night: boolean, saves: object[]}} flags From the command line:
 *   `--claude`'s and `--away`'s modes and the whiteboard switches; `saves` from mockSaves.
 * @returns {object} A fresh /api/state body.
 */
export function startState({
  claude,
  away,
  whiteboardOff,
  oldWhiteboard,
  emptyBoard,
  night,
  saves,
}) {
  // itemCount: null when the daemon is down or (an older build) sends none; 0 is an empty board.
  const itemCount = whiteboardOff || oldWhiteboard ? null : emptyBoard ? 0 : BOARD_ITEMS;
  return {
    orchestrator: startOrchestrator(claude),
    voice: { running: true, phase: "listening", startedBy: "console" },
    board: {
      saves: whiteboardOff ? [] : saves,
      view: whiteboardOff || oldWhiteboard ? null : night ? "night" : "items",
      itemCount,
      online: !whiteboardOff,
    },
    // The model strip's block (signal_console.models); POST /api/models changes it.
    models: MODELS,
    away: awayBlock(away),
    openCommand: OPEN_COMMAND,
  };
}
