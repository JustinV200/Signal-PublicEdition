// What the radar plots: the facts of the live state as blips (shape plus
// label, never colour alone) and as the text readout beside the scope. Pure
// functions of the store state, so the drawing stays dumb.
import { boardViewWords, pendingRows } from "../../state";
import type { AppState } from "../../state";
import { toDotPhase, turnWords } from "../../status";

export type BlipShape = "disc" | "ring" | "square" | "diamond";

export interface Blip {
  id: string;
  shape: BlipShape;
  label: string;
  /** Degrees clockwise from the top. */
  bearingDeg: number;
  /** 0 at the centre, 1 on the outer ring. */
  range: number;
  /** Something is in flight: the blip pulses, `slow` while only agents run (static under reduced motion). */
  pulse?: "normal" | "slow";
}

export interface ReadoutRow {
  label: string;
  value: string;
}

// Bearings are chosen so no two labels share a line: labels point away from
// the side of the scope a blip sits on, towards the middle.
const VOICE_BEARING = 330;
const BOARD_BEARING = 120;
const MID_RANGE = 0.55;
const PENDING_RANGE = 0.85;
const PENDING_FIRST_BEARING = 150;
const PENDING_SPACING_DEG = 45;
const MAX_PENDING_BLIPS = 4;
const MAX_BLIP_LABEL = 24;

function shorten(text: string): string {
  return text.length > MAX_BLIP_LABEL ? `${text.slice(0, MAX_BLIP_LABEL - 1)}…` : text;
}

function orchestratorWords(state: AppState, now: number): string {
  const { server, connection } = state;
  if (connection.status === "offline") return "not connected";
  if (!server) return "connecting";
  if (!server.orchestrator.claimed) return "no session";
  return turnWords(server.orchestrator.turn, now);
}

function voiceWords(state: AppState): string {
  const voice = state.server?.voice;
  if (!voice?.running) return "stopped";
  const by = voice.startedBy ? ` · started by ${voice.startedBy}` : "";
  return `running · ${toDotPhase(voice)}${by}`;
}

/** The blips for the scope. */
export function buildBlips(state: AppState, now: number): Blip[] {
  const { server, busySince } = state;
  const claimed = server?.orchestrator.claimed ?? false;
  const turnState = server?.orchestrator.turn.state;
  // Waiting on agents: a hollow mark with a slow pulse, beside the words.
  const isWaitingOnAgents = claimed && turnState === "agents";
  const voiceRunning = server?.voice.running ?? false;
  const blips: Blip[] = [
    {
      id: "claude",
      shape: claimed && !isWaitingOnAgents ? "disc" : "ring",
      label: claimed ? `CLAUDE · ${orchestratorWords(state, now)}` : "CLAUDE · no session",
      bearingDeg: 0,
      range: 0,
      pulse: busySince !== null ? "normal" : isWaitingOnAgents ? "slow" : undefined,
    },
    {
      id: "voice",
      shape: voiceRunning ? "disc" : "ring",
      label: `VOICE · ${voiceRunning ? toDotPhase(server?.voice) : "stopped"}`,
      bearingDeg: VOICE_BEARING,
      range: MID_RANGE,
    },
    {
      id: "board",
      shape: "square",
      label: `BOARD · ${boardViewWords(server?.board.view ?? null)}`,
      bearingDeg: BOARD_BEARING,
      range: MID_RANGE,
    },
  ];
  // The same pending set as the buttons, so the scope and the views agree.
  pendingRows(state.messages, now)
    .slice(-MAX_PENDING_BLIPS)
    .forEach((row, index) =>
      blips.push({
        id: row.id,
        shape: "diamond",
        label: shorten(row.text),
        bearingDeg: PENDING_FIRST_BEARING + index * PENDING_SPACING_DEG,
        range: PENDING_RANGE,
        pulse: "normal",
      }),
    );
  return blips;
}

/** The text readout beside the scope: the same facts in full. */
export function buildReadout(state: AppState, now: number): ReadoutRow[] {
  const { server } = state;
  const session = server?.orchestrator.claimed ? ` (${server.orchestrator.label})` : "";
  const pending = pendingRows(state.messages, now);
  return [
    { label: "Claude", value: `${orchestratorWords(state, now)}${session}` },
    { label: "Voice hub", value: voiceWords(state) },
    { label: "Board", value: boardViewWords(server?.board.view ?? null) },
    {
      label: "Pending",
      value: pending.length === 0 ? "nothing waiting" : pending.map((row) => row.text).join("; "),
    },
  ];
}
