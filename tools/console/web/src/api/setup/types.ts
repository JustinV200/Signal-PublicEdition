// Wire types for the setup wizard: the requests the page may send to
// POST /api/setup/run (the server turns each into a fixed `setup` CLI call)
// and the shapes of the CLI's JSON answers. tools/setup is the source of
// truth; these only mirror what its commands print.

export type SampleKind = "email" | "writing" | "message" | "code";

export type SetupRequest =
  | { command: "intro" | "list" | "plan" | "status" | "tour" | "wire" }
  | { command: "prereqs" | "choose" | "auto"; tools: string[] }
  | { command: "apply"; tool: string; step: string; answer?: "yes" | "no"; value?: string }
  | { command: "mark"; tool: string; step: string; status: "done" | "skipped" }
  // A step's guide (its registry `doc`) as Markdown; exit 1 with a sentence when there is none.
  | { command: "doc"; tool: string; step: string }
  | { command: "config"; tool: string; set?: Record<string, string> }
  | { command: "samples"; action: "count" | "mail"; kind?: SampleKind }
  | { command: "samples"; action: "files"; paths: string[]; kind: SampleKind }
  | { command: "samples"; action: "paste"; text: string; kind: SampleKind }
  | { command: "samples"; action: "keep"; numbers: number[] };

/** One run: every output line and the exit code (0 done, 1 failed, 2 bad id, 3 needs you). */
export interface SetupResult {
  exit: number;
  lines: string[];
}

export type StepKind =
  "run" | "copy" | "manual" | "confirm" | "email" | "env" | "samples" | "settings";

/** A step's saved status; "" when it never ran. */
export type StepStatus = "done" | "skipped" | "failed" | "";

export interface SetupStep {
  id: string;
  title: string;
  kind: StepKind;
  optional: boolean;
  default: boolean;
  /** Needs the owner's own terminal (a password, Windows Hello, a typed client ID). */
  terminal: boolean;
  /** `setup auto` runs it unasked: a required run or copy step that needs nobody. */
  automatic: boolean;
  text: string;
  doc: string;
  /** A settings step's config group ("" for the tool's main settings). */
  group: string;
  /** The command a run step runs, for display. */
  command: string;
  status: StepStatus;
}

/** A registry tool as `setup list` prints it. */
export interface SetupTool {
  id: string;
  name: string;
  description: string;
  /** Where Pick tools lists it: Core, Everyday, Hardware or Extras ("" for none). */
  group: string;
  /** What setting it up costs, in a few words ("15 min, Google account"). */
  cost: string;
  platform: string;
  supportedHere: boolean;
  /** done, skipped, failed, started or "not set up"; done too for a `detected` tool. */
  status: string;
  /** Among the owner's picks (`setup choose`); a tool whose steps ran unpicked is not. */
  picked: boolean;
  /** Finished, and its servers and hooks are in Claude Code's config. */
  wired: boolean;
  /** Setup has no record of it, and found it already set up; its steps keep reading to do. */
  detected: boolean;
  needs: string[];
  prereqs: string[];
  steps: SetupStep[];
}

/** Where `setup auto` stopped one tool: the step, and whether it needs the owner or failed. */
export interface AutoStop {
  tool: string;
  step: string;
  title: string;
  reason: "needs_you" | "failed";
}

export type SettingType = "str" | "int" | "float" | "bool" | "list" | "times";

/** One editable setting from `setup config <tool> --list`. */
export interface SettingRow {
  id: string;
  group: string;
  value: unknown;
  type: SettingType;
  level: "basic" | "advanced";
  description: string;
  hint: string;
  /** Inclusive bounds of a number setting (null: unbounded); the CLI enforces them. */
  min: number | null;
  max: number | null;
  isPlaceholder: boolean;
}

export type HealthState = "active" | "down" | "not_set_up";

/** A tool's live health from `setup status --json` (System's tools list). */
export interface ToolHealth {
  id: string;
  name: string;
  platform: string;
  supportedHere: boolean;
  setupStatus: string;
  state: HealthState;
  /**
   * What the check found (or why setup isn't finished); "" for a tool never picked. A tool
   * setup has no record of that it found already set up ends `· found already set up`.
   */
  words: string;
  /** What to do, in one sentence, or "": an Active tool may have one too ("not running"). */
  fix: string;
  /** A command that fixes it, runnable as shown from the repo root, or "". */
  command: string;
  /** Finished, and its servers and hooks are in Claude Code's config. */
  wired: boolean;
}

export interface TourSection {
  heading: string;
  body: string;
}

export interface MissingPrereq {
  name: string;
  getIt: string;
}

/** A sent mail offered as a writing sample (`setup samples mail`). */
export interface MailSample {
  number: number;
  subject: string;
  text: string;
}
