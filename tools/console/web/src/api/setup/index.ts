// Public entry point of the setup wizard's api: running setup CLI commands and
// reading their answers.
export { firstJson, jsonDocs, outputParts } from "./jsonDocs";
export type { OutputPart } from "./jsonDocs";
export {
  parseAutoStops,
  parseHealth,
  parseMailSamples,
  parsePrereqs,
  parseSampleCount,
  parseSettings,
  parseTools,
  parseTour,
} from "./parse";
export { openSetupTerminal, runSetup, SetupBusyError } from "./run";
export type {
  AutoStop,
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
