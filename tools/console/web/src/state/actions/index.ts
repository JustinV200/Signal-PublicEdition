// Entry point of state/actions: everything about a request the page sends.
// `store.tsx` imports `./sending` directly instead of this file, because
// `usePendingActions` and `useConfirmGate` here import the store back.
export { actionLabel } from "./actionLabels";
export { actionProgress, PENDING_MAX_MS, pendingActions, pendingRows } from "./actionProgress";
export type { ActionProgress } from "./actionProgress";
export { confirmPrompt } from "./confirmRule";
export { DONE_SHOW_MS, doneClearsAt, lastActionRow } from "./lastActionRow";
export type { Sender } from "./sending";
export { useConfirmGate } from "./useConfirmGate";
export type { ConfirmGate } from "./useConfirmGate";
export { usePendingActions } from "./usePendingActions";
