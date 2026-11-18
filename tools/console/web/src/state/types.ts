// The state package's types: the store's state (AppState), the actions it
// takes (StoreAction) and the pieces they are made of. reducer.ts holds the
// values and the transitions.
import type {
  ActionArgs,
  ActionName,
  ConsoleCheck,
  DeliveryStatus,
  Message,
  ServerEvent,
  ServerState,
  TasksPayload,
  ToolHealth,
  VoiceEvent,
} from "../api";

export type View = "scope" | "chat" | "voice" | "boards" | "tasks" | "system" | "setup";
export type Auth = "checking" | "in" | "out";

/** `since`: epoch ms the server stopped answering (kept across retries until it answers). */
export type Connection =
  | { status: "connecting" }
  | { status: "online" }
  | { status: "offline"; retryAt: number; since: number };

export type InputMode =
  | { kind: "text" }
  | { kind: "confirm"; prompt: string; action: ActionName; args?: ActionArgs }
  | { kind: "command" };

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
  /** Epoch ms the page first heard this row's `done` or `failed`; the result strip's done clears 30 s after it. */
  settledAt?: number;
  origin?: Origin;
  /** The temp id a local send started with; rows key on it so the id swap keeps the DOM node. */
  localId?: string;
}

/** The console's own checks (GET /api/health) as last read; useConsoleHealth fills it. */
export interface ConsoleHealth {
  /** The rows; null before the first good read. */
  checks: ConsoleCheck[] | null;
  /** Why the last read failed; null when it worked. */
  error: string | null;
  loading: boolean;
}

export interface AppState {
  auth: Auth;
  /** Why the page is signed out, in the server's words; null when it never said (or signed in). */
  signOutReason: string | null;
  /** The server's `console open` command line, from the last state or 401; null before either. */
  openCommand: string | null;
  connection: Connection;
  server: ServerState | null;
  /** The orchestrator's task list from the `tasks` event; null until the first one. */
  tasks: TasksPayload | null;
  /** Epoch ms the orchestrator's open turn started (its start hook); null unless `working`. */
  busySince: number | null;
  messages: LocalMessage[];
  /**
   * How many reply and note rows (`isNewsRow`) the owner has seen: set to all of them while
   * Chat is open at the bottom, and bumped for each replayed one stamped before `openedAt`.
   * `chatNewCount` is the rest.
   */
  chatSeenCount: number;
  /** Epoch ms of the page's first server event (before any replay); null until it. */
  openedAt: number | null;
  voiceFeed: VoiceEvent[];
  view: View;
  inputMode: InputMode;
  /** Key (`boardRowKey`) of the `▸` row in the boards view; the to-do row when that board is gone. */
  boardKey: string;
  /** The help panel is open above the view. */
  helpOpen: boolean;
  /** Epoch ms the server last sent anything (an event or a keepalive); null before the first. */
  syncedAt: number | null;
  /** Bumped by the Refresh button; the stream and System's devices poll re-read when it moves. */
  refreshTick: number;
  /** The console's health checks: read at sign-in, on opening System and on Refresh. */
  health: ConsoleHealth;
  /** Bumped by System's Check again; useConsoleHealth re-reads when it moves. */
  healthTick: number;
  /** The tool the setup wizard should open at (a System tools row's button or `#t=`); null: resume. */
  setupTool: string | null;
  /** The failing check a Fix button opened Setup for; its tool page leads with it. Cleared on leaving Setup. */
  setupCheck: ToolHealth | null;
  /** The wizard's page (wizardScreens' screenKey, e.g. `tool:mail`), kept across view switches; null: resume. */
  setupPage: string | null;
  /** What the owner typed in the wizard's fields, by field key, kept across view switches. */
  setupDrafts: Readonly<Record<string, string>>;
  /** The picked tool ids from the last `setup list`; null until one was read. */
  setupPicks: readonly string[] | null;
  /** The console tour's stop while it runs (its last stop while an off-tour tab is open), else null. */
  tourStop: View | null;
}

export type StoreAction =
  | { type: "auth"; auth: Auth; reason?: string; openCommand?: string | null }
  | { type: "connection"; connection: Connection }
  | { type: "server"; event: ServerEvent; now: number }
  | { type: "sendStarted"; message: LocalMessage }
  | { type: "sendAccepted"; tempId: string; id: string }
  | { type: "sendFailed"; tempId: string; error: string }
  | { type: "view"; view: View }
  /** Chat is open and scrolled to the bottom: every row so far is seen. */
  | { type: "chatSeen" }
  | { type: "inputMode"; mode: InputMode }
  | { type: "boardSelect"; key: string }
  | { type: "boardCursorMove"; delta: number }
  | { type: "help"; open: boolean }
  | { type: "alive"; at: number }
  | { type: "refresh" }
  | { type: "health"; health: ConsoleHealth }
  | { type: "recheckHealth" }
  | { type: "openSetup"; tool: string | null; check?: ToolHealth }
  | { type: "setupPage"; page: string }
  /** `text` null forgets the draft (the saved value shows again). */
  | { type: "setupDraft"; key: string; text: string | null }
  | { type: "setupPicks"; picks: readonly string[] }
  | { type: "tour"; stop: View | null };
