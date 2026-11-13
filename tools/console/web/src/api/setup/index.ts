// Public entry point of the setup wizard's api: running setup CLI commands and
// reading their answers.
export { firstJson, jsonDocs } from "./jsonDocs";
export {
  parseHealth,
  parseMailSamples,
  parsePrereqs,
  parseSampleCount,
  parseSettings,
  parseTools,
  parseTour,
} from "./parse";
export { openSetupTerminal, runSetup } from "./run";
export type {
  HealthState,
  MailSample,
  MissingPrereq,
  SampleKind,
  SettingRow,
  SettingType,
  SetupRequest,
  SetupResult,
  SetupStep,
  SetupTool,
  StepKind,
  StepStatus,
  ToolHealth,
  TourSection,
} from "./types";
