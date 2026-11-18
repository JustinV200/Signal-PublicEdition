// Running setup commands from a wizard control: the hook and the wizard's one
// running state, its live log (the CLI's JSON shown as its words), the
// hand-off, where a batch install stopped, and adding the finished tools to
// Claude Code.
export { HandToClaude, handOffPrompt } from "./HandToClaude";
export { exitLook, OutputLog } from "./OutputLog";
export { needsYouWords, readableLines } from "./readableLog";
export { AddResult } from "./AddResult";
export { ADD_TO_CLAUDE, useAddToClaude } from "./useAddToClaude";
export type { AddToClaude } from "./useAddToClaude";
export { useSetupRun } from "./useSetupRun";
export type { SetupRun } from "./useSetupRun";
export {
  ANOTHER_RUNNING,
  buttonLook,
  claim,
  release,
  RUNNING_NOTE,
  RunningProvider,
  useRunningState,
} from "./runningState";
export type { ButtonLook } from "./runningState";
export { AutoStops } from "./AutoStops";
