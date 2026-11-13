// Shape checks for server payloads. The backend is ours, but a response from
// a stale server or a proxy error page must not crash the UI, so every
// payload passes through here before it reaches the store.
import type {
  Delivery,
  DeliveryStatus,
  Message,
  ModelChoices,
  ModelPick,
  ModelsState,
  Note,
  ServerEvent,
  ServerState,
  TurnStateName,
  TurnStatus,
  VoiceEvent,
} from "./types";
import { isDict, isTime, numberOrNull, stringOr } from "./parseFields";
import type { Dict } from "./parseFields";
import { parseTasksPayload } from "./parseTasks";

const TURN_STATES: readonly TurnStateName[] = ["working", "agents", "idle", "stale", "unknown"];

/** The orchestrator's turn; anything malformed (or an older server) reads as `unknown`. */
function parseTurn(value: unknown): TurnStatus {
  const turn = isDict(value) ? value : {};
  const state = TURN_STATES.find((name) => name === turn.state) ?? "unknown";
  return {
    state,
    startedAt: numberOrNull(turn.startedAt),
    lastActivityAt: numberOrNull(turn.lastActivityAt),
    agents: numberOrNull(turn.agents),
    agentsUnsure: Boolean(turn.agentsUnsure),
  };
}

function parsePick(value: unknown): ModelPick | null {
  if (!isDict(value)) return null;
  return { model: stringOr(value.model, null), effort: stringOr(value.effort, null) };
}

/** A list of strings or nulls; anything else in it becomes null (a harmless "unset" entry). */
function choiceList(value: unknown): (string | null)[] {
  return Array.isArray(value) ? value.map((item) => stringOr(item, null)) : [];
}

function parseChoices(value: unknown): ModelChoices {
  const dict = isDict(value) ? value : {};
  return { model: choiceList(dict.model), effort: choiceList(dict.effort) };
}

/** The model strip's block; null when it is missing (an older server) or malformed. */
function parseModels(value: unknown): ModelsState | null {
  if (!isDict(value) || !isDict(value.orchestrator) || !isDict(value.choices)) return null;
  const { orchestrator, choices } = value;
  return {
    orchestrator: { now: parsePick(orchestrator.now), next: parsePick(orchestrator.next) },
    voice: parsePick(value.voice) ?? { model: null, effort: null },
    choices: {
      orchestrator: parseChoices(choices.orchestrator),
      voice: parseChoices(choices.voice),
    },
  };
}

/** Throws if `value` is not a `{id: string}` object; returns it typed. */
function requireId(value: unknown, what: string): Dict & { id: string } {
  if (!isDict(value) || typeof value.id !== "string") throw new Error(`${what}: missing id`);
  return value as Dict & { id: string };
}

/** Checks a GET /api/state body. Throws with a reason on a bad shape. */
export function parseServerState(value: unknown): ServerState {
  if (!isDict(value) || !isDict(value.orchestrator) || !isDict(value.voice) || !isDict(value.board))
    throw new Error("state: missing sections");
  const { orchestrator, voice, board } = value;
  const saves = Array.isArray(board.saves) ? board.saves : [];
  return {
    orchestrator: {
      claimed: Boolean(orchestrator.claimed),
      label: typeof orchestrator.label === "string" ? orchestrator.label : "",
      turn: parseTurn(orchestrator.turn),
    },
    voice: {
      running: Boolean(voice.running),
      phase:
        typeof voice.phase === "string" ? (voice.phase as ServerState["voice"]["phase"]) : null,
      startedBy: typeof voice.startedBy === "string" ? voice.startedBy : null,
    },
    board: {
      saves: saves
        .filter((save): save is Dict => isDict(save) && typeof save.name === "string")
        .map((save) => ({
          name: save.name as string,
          updatedAt: isTime(save.updatedAt) ? save.updatedAt : null,
          description: typeof save.description === "string" ? save.description : null,
          refresher: stringOr(save.refresher, null),
        })),
      view: typeof board.view === "string" ? board.view : null,
      online: Boolean(board.online),
    },
    models: parseModels(value.models),
  };
}

/** The `text` and `at` fields every stream row carries, with safe fallbacks. */
function textAt(dict: Dict): { text: string; at: string | number } {
  return {
    text: typeof dict.text === "string" ? dict.text : "",
    at: isTime(dict.at) ? dict.at : Date.now(),
  };
}

function parseMessage(value: unknown): Message {
  const dict = requireId(value, "message");
  return {
    id: dict.id,
    ...textAt(dict),
    role: dict.role === "you" ? "you" : "claude",
    kind: dict.kind === "action" ? "action" : "chat",
  };
}

function parseNote(value: unknown): Note {
  const dict = requireId(value, "note");
  return { id: dict.id, ...textAt(dict) };
}

const DELIVERY_STATUSES: readonly DeliveryStatus[] = ["sent", "running", "done", "failed"];

// An unknown status reads as `sent`, the most neutral word.
function parseDeliveryStatus(value: unknown): DeliveryStatus {
  return DELIVERY_STATUSES.find((status) => status === value) ?? "sent";
}

function parseDelivery(value: unknown): Delivery {
  const dict = requireId(value, "delivery");
  return {
    id: dict.id,
    // Newer servers give the delivery its own id plus `messageId`; older ones reuse the message id.
    messageId: typeof dict.messageId === "string" ? dict.messageId : dict.id,
    status: parseDeliveryStatus(dict.status),
    error: typeof dict.error === "string" ? dict.error : undefined,
    result: typeof dict.result === "string" ? dict.result : undefined,
  };
}

function parseVoiceEvent(value: unknown): VoiceEvent {
  const dict = requireId(value, "voice");
  const kind = dict.kind === "heard" || dict.kind === "said" ? dict.kind : "note";
  return { id: dict.id, kind, ...textAt(dict) };
}

/** Parses one SSE event by name. Returns null for names this UI does not know. */
export function parseServerEvent(name: string, json: string): ServerEvent | null {
  const value: unknown = JSON.parse(json);
  switch (name) {
    case "state":
      return { type: "state", data: parseServerState(value) };
    case "tasks":
      return { type: "tasks", data: parseTasksPayload(value) };
    case "message":
      return { type: "message", data: parseMessage(value) };
    case "delivery":
      return { type: "delivery", data: parseDelivery(value) };
    case "voice":
      return { type: "voice", data: parseVoiceEvent(value) };
    case "note":
      return { type: "note", data: parseNote(value) };
    default:
      return null;
  }
}

/** Checks a `{id}` reply from POST /api/send or /api/action. */
export function parseIdReply(value: unknown): { id: string } {
  return { id: requireId(value, "reply").id };
}

/** Checks a `{token}` reply from POST /api/login. */
export function parseToken(value: unknown): string {
  if (!isDict(value) || typeof value.token !== "string" || !value.token)
    throw new Error("login: missing token");
  return value.token;
}
