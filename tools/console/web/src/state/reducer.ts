// The console's single reducer: session auth, connection, server snapshot,
// the task list, the message stream with local delivery status (and how many
// of its rows are new to the owner), the voice feed, the console's health
// checks, how fresh the data is (and the Refresh button's tick), the setup
// wizard's page, drafts and picks, the console tour's stop, and UI mode.
import { NOT_SIGNED_IN } from "../api";
import type { ServerEvent, ServerState } from "../api";
import { toMs } from "../time";
import { boardIndexOf, boardRowKey, boardRows, IDLE_ROW_KEY } from "./boards";
import { claudeLink } from "./claude";
import { updateById, upsertSorted } from "./dedupe";
import { tourStops } from "./prefs";
import type { AppState, Auth, Connection, LocalMessage, StoreAction, View } from "./types";

/** Every view, in tab order (Ctrl+1 to Ctrl+6, then Setup on Ctrl+9: see keys/viewKeys.ts). */
export const VIEWS: readonly View[] = [
  "scope",
  "chat",
  "voice",
  "boards",
  "tasks",
  "system",
  "setup",
];
/** Where the console opens and where Esc returns. */
export const HOME_VIEW: View = "scope";

export const initialState: AppState = {
  auth: "checking",
  signOutReason: null,
  openCommand: null,
  connection: { status: "connecting" },
  server: null,
  tasks: null,
  busySince: null,
  messages: [],
  chatSeenCount: 0,
  openedAt: null,
  voiceFeed: [],
  view: HOME_VIEW,
  inputMode: { kind: "text" },
  boardKey: IDLE_ROW_KEY,
  helpOpen: false,
  syncedAt: null,
  refreshTick: 0,
  health: { checks: null, error: null, loading: false },
  healthTick: 0,
  setupTool: null,
  setupCheck: null,
  setupPage: null,
  setupDrafts: {},
  setupPicks: null,
  tourStop: null,
};

/** The first state, opened on `view` (when it names a view) and the wizard at `tool`. */
export function startState(view: string | null, tool: string | null): AppState {
  const known = VIEWS.find((name) => name === view);
  const setupTool = known === "setup" ? tool : null;
  // The tool's page is kept as the wizard's place, as an `openSetup` jump keeps it.
  const setupPage = setupTool === null ? null : `tool:${setupTool}`;
  return { ...initialState, view: known ?? HOME_VIEW, setupTool, setupPage };
}

function applySnapshot(state: AppState, server: ServerState, now: number): AppState {
  const { turn } = server.orchestrator;
  // Busy only while the turn hooks say so (a sent request reads `sent` until the turn starts),
  // and never for a closed session: its last turn will never end.
  const isWorking = turn.state === "working" && claudeLink(server.orchestrator) === "linked";
  const busySince = isWorking ? (turn.startedAt ?? state.busySince ?? now) : null;
  // The command is cached so the page can still show it while the server is down.
  return { ...state, server, busySince, openCommand: server.openCommand ?? state.openCommand };
}

/** The new connection; a retry while still offline keeps when the outage began. */
function nextConnection(previous: Connection, next: Connection): Connection {
  if (next.status === "offline" && previous.status === "offline")
    return { ...next, since: Math.min(previous.since, next.since) };
  return next;
}

/**
 * The sign-out reason after an auth change. Signing in clears it. A focus retry carries
 * no key, so the server's plain "not signed in" (or no reason, as while checking) keeps
 * the more specific reason it followed, e.g. an expired key.
 */
function nextSignOutReason(previous: string | null, auth: Auth, reason?: string): string | null {
  if (auth === "in") return null;
  if (reason === undefined || reason === NOT_SIGNED_IN) return previous ?? reason ?? null;
  return reason;
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
      return addRow(state, event.data);
    case "delivery": {
      const { messageId, status, error, result } = event.data;
      // Applying a replayed delivery again is a no-op, so no event-id bookkeeping is
      // needed; one for a message we never saw (replay cut mid-stream) changes nothing.
      // settledAt keeps the first outcome's time, so a replay never restarts the strip's 30 s.
      const isSettled = status === "done" || status === "failed";
      return {
        ...state,
        messages: updateById(state.messages, messageId, (m) => ({
          ...m,
          delivery: status,
          error,
          result,
          settledAt: m.settledAt ?? (isSettled ? now : undefined),
        })),
      };
    }
    case "voice":
      return { ...state, voiceFeed: upsertSorted(state.voiceFeed, event.data) };
    case "note":
      // Console notices live in the chat stream as their own row kind.
      return addRow(state, { ...event.data, role: "console", kind: "note" });
  }
}

/** A row that can be new to the owner: a reply, an unprompted reply or a note, never their own. */
function isNewsRow(message: LocalMessage): boolean {
  return message.role !== "you";
}

/** Reply and note rows the owner hasn't seen yet: the Chat tab's and the window title's `N new`. */
export function chatNewCount(state: AppState): number {
  return Math.max(0, state.messages.filter(isNewsRow).length - state.chatSeenCount);
}

// Adds a message or note row (a repeated id changes nothing). The server replays its
// history on every connect: a row stamped before the page's first server event was
// there before the page opened, so it counts as seen; the ones after it are new.
function addRow(state: AppState, row: LocalMessage): AppState {
  const messages = upsertSorted(state.messages, row);
  const isAdded = messages.length > state.messages.length;
  const isHistory = state.openedAt === null || toMs(row.at) < state.openedAt;
  const seen = isAdded && isNewsRow(row) && isHistory ? 1 : 0;
  return { ...state, messages, chatSeenCount: state.chatSeenCount + seen };
}

// Chat is open at the bottom: every news row so far is seen. Unchanged state when
// nothing is new, so the scroll handler's repeat dispatches don't re-render.
function markChatSeen(state: AppState): AppState {
  const total = state.messages.filter(isNewsRow).length;
  return total === state.chatSeenCount ? state : { ...state, chatSeenCount: total };
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
      return {
        ...state,
        auth: action.auth,
        signOutReason: nextSignOutReason(state.signOutReason, action.auth, action.reason),
        openCommand: action.openCommand ?? state.openCommand,
      };
    case "connection":
      return { ...state, connection: nextConnection(state.connection, action.connection) };
    case "server":
      // The first one (the sign-in snapshot, or the stream's own) comes before any replay.
      return applyServerEvent(
        { ...state, openedAt: state.openedAt ?? action.now },
        action.event,
        action.now,
      );
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
      return openView(state, action.view);
    case "chatSeen":
      return markChatSeen(state);
    case "inputMode":
      return { ...state, inputMode: action.mode };
    case "boardSelect":
      return { ...state, boardKey: action.key };
    case "boardCursorMove":
      return { ...state, boardKey: movedBoardKey(state, action.delta) };
    case "help":
      return { ...state, helpOpen: action.open };
    case "alive":
      return { ...state, syncedAt: action.at };
    case "refresh":
      return { ...state, refreshTick: state.refreshTick + 1 };
    case "health":
      return { ...state, health: action.health };
    case "recheckHealth":
      return { ...state, healthTick: state.healthTick + 1 };
    case "openSetup":
      // The wizard's own `tool: null` (the jump is done) keeps the check and the page;
      // a new jump replaces both.
      return {
        ...state,
        view: "setup",
        setupTool: action.tool,
        setupCheck: action.check ?? (action.tool === null ? state.setupCheck : null),
        setupPage: action.tool === null ? state.setupPage : `tool:${action.tool}`,
        tourStop: null,
      };
    case "setupPage":
      return { ...state, setupPage: action.page };
    case "setupDraft":
      return withDraft(state, action.key, action.text);
    case "setupPicks":
      return { ...state, setupPicks: action.picks };
    case "tour":
      // Starting or moving the tour opens its stop and closes Help: the two show one at a time.
      if (action.stop === null) return { ...state, tourStop: null };
      return { ...openView(state, action.stop), tourStop: action.stop, helpOpen: false };
  }
}

/**
 * `view` opened. A Fix's check belongs to the visit it opened, so leaving Setup drops it.
 * A running tour follows a tab that is one of its stops; another tab keeps its last stop.
 */
function openView(state: AppState, view: View): AppState {
  const isStop = state.tourStop !== null && tourStops(state.setupPicks).includes(view);
  return {
    ...state,
    view,
    setupCheck: view === "setup" ? state.setupCheck : null,
    tourStop: isStop ? view : state.tourStop,
  };
}

/** A new draft for `key`, or none (null). */
function withDraft(state: AppState, key: string, text: string | null): AppState {
  const drafts = { ...state.setupDrafts };
  if (text === null) delete drafts[key];
  else drafts[key] = text;
  return { ...state, setupDrafts: drafts };
}

// Up/Down from the selected row (the idle row when its board is gone), held to the list.
function movedBoardKey(state: AppState, delta: number): string {
  const rows = boardRows(state.server);
  const index = boardIndexOf(rows, state.boardKey) + delta;
  return boardRowKey(rows[Math.max(0, Math.min(index, rows.length - 1))]);
}
