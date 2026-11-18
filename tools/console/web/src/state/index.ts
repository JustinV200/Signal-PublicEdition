// Public entry point of the state package.
export {
  actionLabel,
  actionProgress,
  confirmPrompt,
  DONE_SHOW_MS,
  doneClearsAt,
  lastActionRow,
  PENDING_MAX_MS,
  pendingActions,
  pendingRows,
  useConfirmGate,
  usePendingActions,
} from "./actions";
export type { ActionProgress, ConfirmGate, Sender } from "./actions";
export {
  boardButtons,
  boardIndexOf,
  boardRowKey,
  FIXED_ROWS,
  boardRows,
  boardTabWords,
  boardViewWords,
  isRowShowing,
  isTodoAvailable,
  NIGHT_REASON,
  NIGHT_VIEW,
  TODO_UNAVAILABLE_REASON,
} from "./boards";
export type { BoardButton, BoardRowInfo } from "./boards";
export { CLAIM_SENTENCE, claudeLink, PASTE_INTO_CLAUDE_NOTE, sendBlockedReason } from "./claude";
export type { ClaudeLink } from "./claude";
export { chatNewCount, HOME_VIEW, initialState, reduce, startState, VIEWS } from "./reducer";
export type {
  AppState,
  Auth,
  Connection,
  ConsoleHealth,
  InputMode,
  LocalDelivery,
  LocalMessage,
  Origin,
  StoreAction,
  View,
} from "./types";
export { readHashLink, startSession, takeHashKey, takeHashLink } from "./session";
export type { HashLink, SessionApi, SessionOutcome } from "./session";
export { StoreProvider, useStore } from "./store";
export {
  currentTheme,
  loadTheme,
  resumeTourStop,
  saveTourStop,
  setTheme,
  tourStops,
} from "./prefs";
export type { Theme } from "./prefs";
