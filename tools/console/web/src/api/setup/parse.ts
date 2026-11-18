// Shape checks for the setup CLI's JSON answers. The server only passes
// through what tools/setup printed; a row missing its id is dropped and other
// fields fall back, so a newer CLI field never breaks the page.
import { dictList, isDict, numberOrNull, stringOr } from "../parseFields";
import type { Dict } from "../parseFields";
import type {
  AutoStop,
  HealthState,
  MailSample,
  MissingPrereq,
  SettingRow,
  SettingType,
  SetupStep,
  SetupTool,
  StepKind,
  StepStatus,
  ToolHealth,
  TourSection,
} from "./types";

const STEP_KINDS: readonly StepKind[] = [
  "run",
  "copy",
  "manual",
  "confirm",
  "email",
  "env",
  "samples",
  "settings",
];
const STEP_STATUSES: readonly StepStatus[] = ["done", "skipped", "failed", ""];
const SETTING_TYPES: readonly SettingType[] = ["str", "int", "float", "bool", "list", "times"];
const HEALTH_STATES: readonly HealthState[] = ["active", "down", "not_set_up"];

type IdDict = Dict & { id: string };

function pick<T extends string>(options: readonly T[], value: unknown, fallback: T): T {
  return options.find((option) => option === value) ?? fallback;
}

function strings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

/** Rows of `value` that have a string id, mapped by `parse`. */
function rows<T>(value: unknown, parse: (dict: IdDict) => T): T[] {
  return dictList(value)
    .filter((dict): dict is IdDict => typeof dict.id === "string")
    .map(parse);
}

function parseStep(dict: IdDict): SetupStep {
  return {
    id: dict.id,
    title: stringOr(dict.title, dict.id),
    kind: pick(STEP_KINDS, dict.kind, "manual"),
    optional: dict.optional === true,
    default: dict.default !== false,
    terminal: dict.terminal === true,
    automatic: dict.automatic === true,
    text: stringOr(dict.text, ""),
    doc: stringOr(dict.doc, ""),
    group: stringOr(dict.group, ""),
    command: stringOr(dict.command, ""),
    status: pick(STEP_STATUSES, dict.status, ""),
  };
}

/** `setup list`: every registry tool with its steps. */
export function parseTools(value: unknown): SetupTool[] {
  return rows(value, (dict) => ({
    id: dict.id,
    name: stringOr(dict.name, dict.id),
    description: stringOr(dict.description, ""),
    group: stringOr(dict.group, ""),
    cost: stringOr(dict.cost, ""),
    platform: stringOr(dict.platform, ""),
    supportedHere: dict.supported_here !== false,
    status: stringOr(dict.status, "not set up"),
    picked: dict.picked === true,
    wired: dict.wired === true,
    needs: strings(dict.needs),
    prereqs: strings(dict.prereqs),
    steps: rows(dict.steps, parseStep),
  }));
}

/** `setup auto`'s closing JSON: where each tool stopped (a stop without a tool or step is dropped). */
export function parseAutoStops(value: unknown): AutoStop[] {
  const stopped = isDict(value) ? value.stopped : [];
  return dictList(stopped)
    .filter((dict) => typeof dict.tool === "string" && typeof dict.step === "string")
    .map((dict) => ({
      tool: stringOr(dict.tool, ""),
      step: stringOr(dict.step, ""),
      title: stringOr(dict.title, stringOr(dict.step, "")),
      reason: dict.reason === "failed" ? "failed" : "needs_you",
    }));
}

/** `setup config <tool> --list`: the tool's settings and unnamed placeholders. */
export function parseSettings(value: unknown): SettingRow[] {
  return rows(value, (dict) => ({
    id: dict.id,
    group: stringOr(dict.group, ""),
    value: dict.value,
    type: pick(SETTING_TYPES, dict.type, "str"),
    level: dict.level === "advanced" ? "advanced" : "basic",
    description: stringOr(dict.description, ""),
    hint: stringOr(dict.hint, ""),
    min: numberOrNull(dict.min),
    max: numberOrNull(dict.max),
    isPlaceholder: dict.is_placeholder === true,
  }));
}

/** `setup status --json`: each tool's health; a null `fix` or `command` reads as "". */
export function parseHealth(value: unknown): ToolHealth[] {
  return rows(value, (dict) => ({
    id: dict.id,
    name: stringOr(dict.name, dict.id),
    platform: stringOr(dict.platform, ""),
    supportedHere: dict.supported_here !== false,
    setupStatus: stringOr(dict.setup_status, ""),
    state: pick(HEALTH_STATES, dict.state, "not_set_up"),
    words: stringOr(dict.words, ""),
    fix: stringOr(dict.fix, ""),
    command: stringOr(dict.command, ""),
    wired: dict.wired === true,
  }));
}

/** `setup tour --json`: GUIDE.md's sections. */
export function parseTour(value: unknown): TourSection[] {
  return dictList(value).map((dict) => ({
    heading: stringOr(dict.heading, ""),
    body: stringOr(dict.body, ""),
  }));
}

/** `setup prereqs`: the programs still missing. */
export function parsePrereqs(value: unknown): MissingPrereq[] {
  return dictList(value).map((dict) => ({
    name: stringOr(dict.name, "?"),
    getIt: stringOr(dict.get_it, ""),
  }));
}

/** `setup samples mail`: the numbered sent mails. */
export function parseMailSamples(value: unknown): MailSample[] {
  return dictList(value).map((dict, index) => ({
    number: numberOrNull(dict.number) ?? index + 1,
    subject: stringOr(dict.subject, ""),
    text: stringOr(dict.text, ""),
  }));
}

/** The `{samples, target}` count every samples command ends with. */
export function parseSampleCount(value: unknown): { samples: number; target: string } {
  if (!isDict(value)) return { samples: 0, target: "" };
  return { samples: numberOrNull(value.samples) ?? 0, target: stringOr(value.target, "") };
}
