// Public entry point of the setup wizard view (and the health lists, Add to
// Claude Code runner and its result line that System's CONSOLE and TOOLS
// groups share, and the Setup tab rule the shell reads).
export {
  checkCounts,
  consoleItem,
  consoleRowKey,
  HealthList,
  healthAction,
  healthCounts,
  healthLook,
  healthRowId,
  ToolHealthList,
} from "./health";
export { SetupView } from "./SetupView";
export { useSetupQuery } from "./useSetupQuery";
export { useSetupTab } from "./useSetupTab";
export {
  buildScreens,
  openIndex,
  pageToKeep,
  resumeIndex,
  screenKey,
  showsSetupTab,
} from "./wizardScreens";
export { stripSections } from "./head";
export { changedValues, fieldKind, valueText } from "./settings";
export { AddResult, ANOTHER_RUNNING, buttonLook, handOffPrompt, useAddToClaude } from "./run";
