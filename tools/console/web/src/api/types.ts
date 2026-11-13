// Wire types for the console backend (tools/console/src). Everything the
// server sends is untrusted until api/parse.ts has checked its shape.

/** `starting`: the hub process is up but not listening yet (loading its models). */
export type VoicePhase = "starting" | "listening" | "thinking" | "speaking" | "off";

/** The orchestrator's turn, from its turn hooks (start, end, idle) and usage.json's agents. */
export type TurnStateName = "working" | "agents" | "idle" | "stale" | "unknown";

export interface TurnStatus {
  state: TurnStateName;
  /** Epoch ms the open turn started (the hook's stamp); null with no turn open. */
  startedAt: number | null;
  /** Epoch ms of the last hook from the session; null before any. */
  lastActivityAt: number | null;
  /** Running subagents; null when unknown. */
  agents: number | null;
  /** usage.json and the last Stop disagree on `agents` (it is the lower one). */
  agentsUnsure: boolean;
}

export interface OrchestratorState {
  claimed: boolean;
  label: string;
  turn: TurnStatus;
}

export interface VoiceState {
  running: boolean;
  phase: VoicePhase | null;
  startedBy: string | null;
}

export interface BoardSave {
  name: string;
  updatedAt: string | number | null;
  /** One line about what is on the board; null until the backend passes it through. */
  description: string | null;
  /** What can redraw it from live data (`tasks` or `todo`); null means no Update button. */
  refresher: string | null;
}

export interface BoardState {
  saves: BoardSave[];
  /** The whiteboard's view, `"todo"` or `"items"`; null when it is off or an older build reports none. */
  view: string | null;
  /** The whiteboard daemon answered. False until the first board request starts it. */
  online: boolean;
}

/** A model and effort; null means unknown (now) or not set (a pick). */
export interface ModelPick {
  model: string | null;
  effort: string | null;
}

/** The lists a pick's index points into; null is "use my user settings". */
export interface ModelChoices {
  model: (string | null)[];
  effort: (string | null)[];
}

export type ModelTarget = "orchestrator" | "voice";
export type ModelField = keyof ModelChoices;

export interface ModelsState {
  orchestrator: {
    /** The claimed session's model and last effort; null with no claim. */
    now: ModelPick | null;
    /** settings.local.json's pick for new Signal sessions; null when the file can't be read. */
    next: ModelPick | null;
  };
  /** Voice's pick; null fields mean audiohub.toml decides. */
  voice: ModelPick;
  choices: Record<ModelTarget, ModelChoices>;
}

export interface ServerState {
  orchestrator: OrchestratorState;
  voice: VoiceState;
  board: BoardState;
  /** Null from an older server. */
  models: ModelsState | null;
}

/** `console` is the UI's own `note` rows; the server never sends it as a message role. */
export type MessageRole = "you" | "claude" | "console";
export type MessageKind = "chat" | "action" | "note";

export interface Message {
  id: string;
  role: MessageRole;
  text: string;
  at: string | number;
  kind: MessageKind;
}

/** A console notice, e.g. the orchestrator claim changed; shown in the chat stream. */
export interface Note {
  id: string;
  text: string;
  at: string | number;
}

/**
 * `sent`: a typed message reached the orchestrator. A button's action goes
 * `running` (the server is running it), then `done` or `failed`.
 */
export type DeliveryStatus = "sent" | "running" | "done" | "failed";

export interface Delivery {
  /** The delivery event's own id (replayed events repeat it). */
  id: string;
  /** The message this delivery is about. */
  messageId: string;
  status: DeliveryStatus;
  error?: string;
  /** What a `done` action did, in words. */
  result?: string;
}

export type VoiceEventKind = "heard" | "said" | "note";

export interface VoiceEvent {
  id: string;
  kind: VoiceEventKind;
  text: string;
  at: string | number;
}

/** One task in the Tasks page, from tasks.json via the `tasks` event. */
export type TaskStatus = "review" | "building" | "needs_you" | "queued" | "done";

export interface TaskInfo {
  id: string;
  name: string;
  pct: number;
  status: TaskStatus;
  /** The board's status number: 1 review, 2 building, 3 needs you, 4 queued, 5 done. */
  number: number;
  next: string;
  /** What the owner must do; set on `needs_you` tasks. */
  you: string;
  updatedAt: string;
}

export interface UsageWindow {
  usedPct: number;
  resetsAt: string;
}

export interface UsageInfo {
  /** Null when unknown or already reset. */
  fiveHour: UsageWindow | null;
  sevenDay: UsageWindow | null;
  agents: number;
  /** The usage file's last write; null when it has none. */
  updatedAt: string | null;
}

/** The `tasks` event: tasks in display order plus the usage line. */
export interface TasksPayload {
  updatedAt: string | null;
  /** review, building and needs_you, most finished first. */
  active: TaskInfo[];
  queued: TaskInfo[];
  /** Newest first. */
  done: TaskInfo[];
  needsYou: number;
  overallPct: number | null;
  /** Null while usage.json has never been read. */
  usage: UsageInfo | null;
}

export type DeviceState = "on" | "off" | "unknown";

/** One row of the Connected devices page; `words` always says the state. */
export interface DeviceRow {
  id: string;
  name: string;
  state: DeviceState;
  words: string;
  /** Only the webcam: its live stream can be shown. */
  canOpen: boolean;
}

export type AwayState = "here" | "away" | "asleep";

export interface AwayInfo {
  state: AwayState;
  /** When away mode ends (ISO); null while here. */
  endsAt: string | null;
  note: string;
}

/** GET /api/devices. `away` is null when the brief's state can't be read. */
export interface DevicesPayload {
  devices: DeviceRow[];
  away: AwayInfo | null;
}

/** One parsed SSE event from GET /api/events. */
export type ServerEvent =
  | { type: "state"; data: ServerState }
  | { type: "tasks"; data: TasksPayload }
  | { type: "message"; data: Message }
  | { type: "delivery"; data: Delivery }
  | { type: "voice"; data: VoiceEvent }
  | { type: "note"; data: Note };

export type ActionName =
  | "voice.start"
  | "voice.stop"
  | "board.load"
  | "board.todo"
  | "board.idle"
  | "board.realign"
  | "board.calibrate"
  | "board.update";

export interface ActionArgs {
  name?: string;
  /** board.update on the to-do list, which is not a save. */
  view?: "todo";
}
