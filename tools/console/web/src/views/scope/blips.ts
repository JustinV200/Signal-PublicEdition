// What the radar plots: the facts of the live state as blips (shape plus
// label, never colour alone), each in its subsystem's sector and opening that
// subsystem's view. Claude sits at the centre; Voice, the board and their
// pending requests sit at the time since they last did something; tasks at
// their progress, those waiting on the owner as one count (taskBlips.ts). Pure
// functions of the store state, so the drawing stays dumb. readout.ts words
// the same facts as text rows.
import { boardViewWords, claudeLink, pendingRows } from "../../state";
import type { AppState, LocalMessage, View } from "../../state";
import { toDotPhase, turnCauseWords } from "../../status";
import { toMs } from "../../time";
import { ageRange, SECTORS } from "./radar";
import type { Blip, Sector } from "./radar";
import { taskBlips } from "./taskBlips";

// Pending requests sit either side of their subsystem's blip, these many degrees off its middle.
const REQUEST_OFFSETS_DEG = [-25, 25, -38, 38];

/** Claude's session and turn in words; the readout shares it (and adds its own offline suffix). */
export function claudeWords(state: AppState, now: number): string {
  const { server, connection } = state;
  if (!server) return "connecting";
  const link = claudeLink(server.orchestrator);
  if (link === "none") return "no session";
  if (link === "closed") return "session closed";
  // Offline, the turn is as last known: its clock stops at the drop instead of counting on.
  const at = connection.status === "offline" ? connection.since : now;
  // With the cause, as the status line words it (`state unknown · turn hook missing`).
  return turnCauseWords(server.orchestrator.turn, state.health.checks, at);
}

/** What the projector shows in words, `off` while the whiteboard is; the radar and the readout share it. */
export function boardWords(state: AppState): string {
  const board = state.server?.board;
  return board?.online ? boardViewWords(board.view) : "off";
}

/** The view a button's row belongs to: Voice's buttons are `voice.*`, the rest are the whiteboard's. */
export function actionView(row: LocalMessage): View {
  return row.origin?.kind === "action" && row.origin.action.startsWith("voice.")
    ? "voice"
    : "boards";
}

// The radar's label says outright when the stream is down.
function orchestratorWords(state: AppState, now: number): string {
  return state.connection.status === "offline" ? "not connected" : claudeWords(state, now);
}

const middleOf = (sector: Sector) => (sector.fromDeg + sector.toDeg) / 2;
const ageAt = (at: string | number | undefined, now: number) =>
  at === undefined ? null : now - toMs(at);

function claudeBlip(state: AppState, now: number): Blip {
  const { server, busySince } = state;
  // A disc only for a session that is claimed and still open.
  const linked = server ? claudeLink(server.orchestrator) === "linked" : false;
  // Waiting on agents: a hollow mark with a slow pulse, beside the words.
  const isWaitingOnAgents = linked && server?.orchestrator.turn.state === "agents";
  return {
    id: "claude",
    shape: linked && !isWaitingOnAgents ? "disc" : "ring",
    label: `CLAUDE · ${orchestratorWords(state, now)}`,
    bearingDeg: 0,
    range: 0,
    pulse: busySince !== null ? "normal" : isWaitingOnAgents ? "slow" : undefined,
    view: "chat",
    isLabelPinned: true,
  };
}

// Voice and the board: a hollow ring while off; range from their last activity
// (Voice's newest feed event, the board's newest button row).
function subsystemBlips(state: AppState, now: number): Blip[] {
  const { server } = state;
  const voiceRunning = server?.voice.running ?? false;
  const boardOn = server?.board.online ?? false;
  const lastBoardRow = state.messages.findLast(
    (row) => row.kind === "action" && actionView(row) === "boards",
  );
  return [
    {
      id: "voice",
      shape: voiceRunning ? "disc" : "ring",
      label: `VOICE · ${voiceRunning ? toDotPhase(server?.voice) : "stopped"}`,
      bearingDeg: middleOf(SECTORS.voice),
      range: ageRange(ageAt(state.voiceFeed.at(-1)?.at, now)),
      view: "voice",
    },
    {
      id: "board",
      shape: boardOn ? "square" : "ring",
      label: `BOARD · ${boardWords(state)}`,
      bearingDeg: middleOf(SECTORS.board),
      range: ageRange(ageAt(lastBoardRow?.at, now)),
      view: "boards",
    },
  ];
}

// The same pending set as the buttons, so the scope and the views agree; each
// beside its subsystem, at the time since it was sent.
function requestBlips(state: AppState, now: number): Blip[] {
  const used = { voice: 0, boards: 0 };
  return pendingRows(state.messages, now).flatMap((row) => {
    const view = actionView(row) === "voice" ? "voice" : "boards";
    const offset = REQUEST_OFFSETS_DEG[used[view]++];
    if (offset === undefined) return [];
    const sector = view === "voice" ? SECTORS.voice : SECTORS.board;
    return [
      {
        id: row.id,
        shape: "diamond",
        label: row.text,
        bearingDeg: middleOf(sector) + offset,
        range: ageRange(ageAt(row.at, now)),
        pulse: "normal",
        view,
      } satisfies Blip,
    ];
  });
}

/**
 * The blips for the scope, in label priority: Claude, then the count of tasks
 * that need the owner (each label has a fixed spot, so they go first and
 * nothing ever covers them), Voice, the board, pending requests, then the other
 * tasks (whose labels a crowded face hides first; the Tasks view lists them all).
 */
export function buildBlips(state: AppState, now: number): Blip[] {
  const tasks = taskBlips(state.tasks);
  return [
    claudeBlip(state, now),
    ...tasks.filter((blip) => blip.isUrgent),
    ...subsystemBlips(state, now),
    ...requestBlips(state, now),
    ...tasks.filter((blip) => !blip.isUrgent),
  ];
}
