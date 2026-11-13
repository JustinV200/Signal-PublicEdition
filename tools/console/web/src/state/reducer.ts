// The console's single reducer: session auth, connection, server snapshot,
// the task list, the message stream with local delivery status, the voice
// feed, how fresh the data is (and the Refresh button's tick), and UI mode.
import type {
  ActionArgs,
  ActionName,
  DeliveryStatus,
  Message,
  ServerEvent,
  ServerState,
  TasksPayload,
  VoiceEvent,
} from "../api";
import { boardRowCount } from "./boards";
import { updateById, upsertSorted } from "./dedupe";

export type View =
  "scope" | "chat" | "voice" | "boards" | "tasks" | "devices" | "models" | "tools" | "setup";
/** Every view, in tab order (Ctrl+1 to Ctrl+9). */
export const VIEWS: readonly View[] = [
  "scope",
  "chat",
  "voice",
  "boards",
  "tasks",
  "devices",
  "models",
  "tools",
  "setup",
];
/** Where the console opens and where Esc returns. */
export const HOME_VIEW: View = "scope";
export type Auth = "checking" | "in" | "out";

export type Connection =
  { status: "connecting" } | { status: "online" } | { status: "offline"; retryAt: number };

export type InputMode =
  { kind: "text" } | { kind: "confirm"; prompt: string; action: ActionName } | { kind: "command" };

/** What a local message asked the server to do; `[retry]` re-sends it. */
export type Origin =
  { kind: "text"; text: string } | { kind: "action"; action: ActionName; args?: ActionArgs };

/** `sending` is local (the POST is out); the rest come from `delivery` events. */
export type LocalDelivery = "sending" | DeliveryStatus;

export interface LocalMessage extends Message {
  delivery?: LocalDelivery;
  error?: string;
  /** What a finished action did, in words (from its `done` delivery). */
  result?: string;
  origin?: Origin;
  /** The temp id a local send started with; rows key on it so the id swap keeps the DOM node. */
  localId?: string;
}

export interface AppState {
  auth: Auth;
  connection: Connection;
  server: ServerState | null;
  /** The orchestrator's task list from the `tasks` event; null until the first one. */
  tasks: TasksPayload | null;
  /** Epoch ms the orchestrator's open turn started (its start hook); null unless `working`. */
  busySince: number | null;
  messages: LocalMessage[];
  voiceFeed: VoiceEvent[];
  view: View;
  inputMode: InputMode;
  /** Index of the `▸` row in the boards view (0 is the todo list). */
  boardCursor: number;
  /** The help panel is open above the view. */
  helpOpen: boolean;
  /** Epoch ms the server last sent anything (an event or a keepalive); null before the first. */
  syncedAt: number | null;
  /** Bumped by the Refresh button; the stream and the devices poll re-read when it moves. */
  refreshTick: number;
  /** The tool the setup wizard should open at (a Tools page button or `#t=`); null: resume. */
  setupTool: string | null;
  /** The console tour's stop while it runs (an index into the tour's stops), else null. */
  tourStep: number | null;
}

export type StoreAction =
  | { type: "auth"; auth: Auth }
  | { type: "connection"; connection: Connection }
  | { type: "server"; event: ServerEvent; now: number }
  | { type: "sendStarted"; message: LocalMessage }
  | { type: "sendAccepted"; tempId: string; id: string }
  | { type: "sendFailed"; tempId: string; error: string }
  | { type: "view"; view: View }
  | { type: "inputMode"; mode: InputMode }
  | { type: "boardCursor"; index: number }
  | { type: "boardCursorMove"; delta: number }
  | { type: "help"; open: boolean }
  | { type: "alive"; at: number }
  | { type: "refresh" }
  | { type: "openSetup"; tool: string | null }
  | { type: "tour"; step: number | null };

export const initialState: AppState = {
  auth: "checking",
  connection: { status: "connecting" },
  server: null,
  tasks: null,
  busySince: null,
  messages: [],
  voiceFeed: [],
  view: HOME_VIEW,
  inputMode: { kind: "text" },
  boardCursor: 0,
  helpOpen: false,
  syncedAt: null,
  refreshTick: 0,
  setupTool: null,
  tourStep: null,
};

/** The first state, opened on `view` (when it names a view) and the wizard at `tool`. */
export function startState(view: string | null, tool: string | null): AppState {
  const known = VIEWS.find((name) => name === view);
  return { ...initialState, view: known ?? HOME_VIEW, setupTool: known === "setup" ? tool : null };
}

function applySnapshot(state: AppState, server: ServerState, now: number): AppState {
  const { turn } = server.orchestrator;
  // Busy only while the turn hooks say so: a sent request reads `sent` until the turn starts.
  const busySince = turn.state === "working" ? (turn.startedAt ?? state.busySince ?? now) : null;
  const boardCursor = Math.min(state.boardCursor, boardRowCount(server) - 1);
  return { ...state, server, busySince, boardCursor };
}

function applyServerEvent(state: AppState, event: ServerEvent, now: number): AppState {
  switch (event.type) {
    case "state":
      return applySnapshot(state, event.data, now);
    case "tasks":
      // A full snapshot each time, like `state`.
      return { ...state, tasks: event.data };
    case "message":
      // First-wins dedupe keeps a local row's delivery/origin through the server echo.
      return { ...state, messages: upsertSorted(state.messages, event.data) };
    case "delivery": {
      const { messageId, status, error, result } = event.data;
      // Applying a replayed delivery again is a no-op, so no event-id bookkeeping is
      // needed; one for a message we never saw (replay cut mid-stream) changes nothing.
      return {
        ...state,
        messages: updateById(state.messages, messageId, (m) => ({
          ...m,
          delivery: status,
          error,
          result,
        })),
      };
    }
    case "voice":
      return { ...state, voiceFeed: upsertSorted(state.voiceFeed, event.data) };
    case "note":
      // Console notices live in the chat stream as their own row kind.
      return {
        ...state,
        messages: upsertSorted(state.messages, { ...event.data, role: "console", kind: "note" }),
      };
  }
}

// The POST reply may arrive after the SSE echo: then the echo already holds the
// real id, so drop the temp row and move its origin/delivery onto the echo.
function acceptSend(state: AppState, tempId: string, id: string): AppState {
  const temp = state.messages.find((m) => m.id === tempId);
  if (!temp) return state;
  const echo = state.messages.find((m) => m.id === id);
  const merged: LocalMessage = {
    ...(echo ?? temp),
    id,
    localId: tempId,
    origin: temp.origin,
    delivery: echo?.delivery ?? temp.delivery,
  };
  const others = state.messages.filter((m) => m.id !== tempId && m.id !== id);
  return { ...state, messages: upsertSorted(others, merged) };
}

/** Pure state transition. `now` rides on server actions so the reducer never reads the clock. */
export function reduce(state: AppState, action: StoreAction): AppState {
  switch (action.type) {
    case "auth":
      return { ...state, auth: action.auth };
    case "connection":
      return { ...state, connection: action.connection };
    case "server":
      return applyServerEvent(state, action.event, action.now);
    case "sendStarted":
      return { ...state, messages: upsertSorted(state.messages, action.message) };
    case "sendAccepted":
      return acceptSend(state, action.tempId, action.id);
    case "sendFailed":
      return {
        ...state,
        messages: updateById(state.messages, action.tempId, (m) => ({
          ...m,
          delivery: "failed",
          error: action.error,
        })),
      };
    case "view":
      return { ...state, view: action.view };
    case "inputMode":
      return { ...state, inputMode: action.mode };
    case "boardCursor":
      return { ...state, boardCursor: clampCursor(state, action.index) };
    case "boardCursorMove":
      return { ...state, boardCursor: clampCursor(state, state.boardCursor + action.delta) };
    case "help":
      return { ...state, helpOpen: action.open };
    case "alive":
      return { ...state, syncedAt: action.at };
    case "refresh":
      return { ...state, refreshTick: state.refreshTick + 1 };
    case "openSetup":
      return { ...state, view: "setup", setupTool: action.tool, tourStep: null };
    case "tour":
      return { ...state, tourStep: action.step };
  }
}

function clampCursor(state: AppState, index: number): number {
  return Math.max(0, Math.min(index, boardRowCount(state.server) - 1));
}
