// The mock setup CLI's tool settings (`setup config <tool>`): a live copy of
// each tool's settings rows, listed the way cli/config.py prints them and
// changed the way settings/store.py's set_value checks typed text (parse,
// range, placeholder). Only the browser has settings in the mock. Used by
// mock-setup-cli.mjs, which prints the answers and keeps step progress.

// Values the shipped examples use that the owner must replace (settings/placeholders.py).
const PLACEHOLDER = /example\.(?:edu|com|org)|YOUR[_-]|<[^<>\n]+>|TODO\(/;
// A 24-hour time, as settings/values.py checks `times` items.
const TIME = /^([01]\d|2[0-3]):[0-5]\d$/;
const EMPTY_LIST_WORDS = ["none", "[]"];
const BOOL_WORDS = { yes: true, true: true, y: true, no: false, false: false, n: false };
const BROWSER_FILE = "tools/browser/browser.toml";

/** A settings row as `setup config --list` prints it (is_placeholder is worked out when listed). */
const row = (id, type, value, extra = {}) => ({
  id,
  file: BROWSER_FILE,
  group: "",
  value,
  default: value,
  type,
  level: "basic",
  description: "",
  hint: "",
  min: null,
  max: null,
  ...extra,
});

// One row per setting type, one advanced, and the placeholder the settings step stops on.
const SETTINGS = {
  browser: [
    row("policy.allow", "list", ["github.com", "*.wikipedia.org"], {
      description: "Sites the browser may open",
      hint: "hosts, comma-separated, e.g. github.com, *.wikipedia.org; none for none",
    }),
    row("downloads.enabled", "bool", true, {
      description: "Save downloads to the tool's downloads folder",
      hint: "yes or no",
    }),
    row("downloads.max_mb", "int", 50, {
      description: "Largest download to keep, in MB",
      min: 1,
      max: 500,
    }),
    row("downloads.cleanup_at", "times", ["03:00"], {
      description: "When to clear old downloads each day",
    }),
    row("example_setting", "str", "YOUR_VALUE", {
      description: "A value the example ships as a placeholder",
    }),
    row("page.timeout_s", "float", 7.5, {
      level: "advanced",
      description: "Seconds to wait for a page to load",
      min: 1,
      max: 120,
    }),
  ],
};

const settings = structuredClone(SETTINGS);
// Tools whose config file the settings step already made from its example.
const created = new Set();

const isPlaceholder = (value) =>
  Array.isArray(value)
    ? value.some(isPlaceholder)
    : typeof value === "string" && PLACEHOLDER.test(value);

/** Comma-separated items; "none" or [] is the empty list. */
function items(text) {
  if (EMPTY_LIST_WORDS.includes(text.toLowerCase())) return [];
  return text
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
}

/** `raw` as a `type` value (settings/values.py parse). Throws Error with words the owner can act on. */
function parseValue(type, raw) {
  const text = raw.trim();
  if (type === "int") {
    if (!/^-?\d+$/.test(text)) throw new Error(`'${text}' isn't a whole number`);
    return Number(text);
  }
  if (type === "float") {
    if (!text || Number.isNaN(Number(text))) throw new Error(`'${text}' isn't a number`);
    return Number(text);
  }
  if (type === "bool") {
    // hasOwn, not `in`: "constructor" is in every object.
    if (!Object.hasOwn(BOOL_WORDS, text.toLowerCase())) throw new Error("type yes or no");
    return BOOL_WORDS[text.toLowerCase()];
  }
  if (type === "list") return items(text);
  if (type === "times") {
    const times = items(text);
    if (!times.length || times.some((time) => !TIME.test(time)))
      throw new Error("give one or more 24-hour times like 07:00, 14:30");
    return times;
  }
  if (!text) throw new Error("the value can't be empty");
  return text;
}

/** Checks `text` for `setting` and stores it, or throws why it was refused (store.set_value). */
function setValue(setting, text) {
  const value = parseValue(setting.type, text);
  const { min, max } = setting;
  if ((min !== null && value < min) || (max !== null && value > max))
    throw new Error(`${value} is out of range (lowest ${min}, highest ${max})`);
  if (isPlaceholder(value))
    throw new Error(`'${text}' is still a placeholder; give your real value`);
  setting.value = value;
}

/** True when the tool has settings in the mock (`setup config` answers "no settings" otherwise). */
export const hasSettings = (toolId) => toolId in settings;

/** `setup config <tool> --list`: every row with is_placeholder filled in. */
export function listSettings(toolId) {
  return settings[toolId].map((setting) => ({
    ...setting,
    is_placeholder: isPlaceholder(setting.value),
  }));
}

/** Ids of the placeholders left in `group` of the tool's config ([] for a tool without settings). */
export function placeholdersLeft(toolId, group) {
  return (settings[toolId] ?? [])
    .filter((setting) => setting.group === group && isPlaceholder(setting.value))
    .map((setting) => setting.id);
}

/** The config file the settings step makes the first time it runs, else null (already there). */
export function createConfigFile(toolId) {
  if (created.has(toolId) || !hasSettings(toolId)) return null;
  created.add(toolId);
  return settings[toolId][0].file;
}

/**
 * Sets each id to its typed text, the way `setup config <tool> --set` does.
 *
 * @param {string} toolId A tool with settings (check hasSettings first).
 * @param {Record<string, string>} values Setting id to the text typed for it.
 * @returns {{set: string[], errors: Record<string, string>, groups: Set<string>}} The ids
 *   set, why each refused one was refused, and the groups of the changed settings.
 */
export function setSettings(toolId, values) {
  const set = [];
  const errors = {};
  const groups = new Set();
  for (const [id, text] of Object.entries(values)) {
    const setting = settings[toolId].find((candidate) => candidate.id === id);
    try {
      if (!setting)
        throw new Error(`${toolId} has no setting '${id}'; see setup config ${toolId} --list`);
      setValue(setting, text);
      set.push(id);
      groups.add(setting.group);
    } catch (error) {
      errors[id] = error.message;
    }
  }
  return { set, errors, groups };
}
