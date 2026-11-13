// Maps a tool's settings schema (rows from `setup config <tool> --list`) to
// form fields, and back to the `--set id=value` text the setup CLI parses
// (tools/setup settings/values.py: yes/no for bools, comma-separated lists
// and times). The CLI does the real validation; this only shapes the form.
import type { SettingRow, SettingType } from "../../../api";

export type FieldKind = "checkbox" | "number" | "text";

const KIND_BY_TYPE: Record<SettingType, FieldKind> = {
  bool: "checkbox",
  int: "number",
  float: "number",
  str: "text",
  list: "text",
  times: "text",
};
// Shown under a field whose schema gives no hint of its own.
const TYPE_HINTS: Partial<Record<SettingType, string>> = {
  list: "comma-separated; none for an empty list",
  times: "24-hour times, comma-separated, e.g. 07:00, 18:00",
  bool: "",
};

/** The input a setting gets. */
export function fieldKind(type: SettingType): FieldKind {
  return KIND_BY_TYPE[type];
}

/** A setting's current value as the text the CLI takes back ("" when unset). */
export function valueText(value: unknown, type: SettingType): string {
  if (value === null || value === undefined) return "";
  if (type === "bool" || typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return value.map(String).join(", ");
  return String(value);
}

/** The hint under a field: the schema's, else one for its type. */
export function fieldHint(row: SettingRow): string {
  return row.hint || TYPE_HINTS[row.type] || "";
}

/** The `--set` values for the fields whose draft differs from the saved value. */
export function changedValues(
  rows: readonly SettingRow[],
  drafts: Readonly<Record<string, string>>,
): Record<string, string> {
  const changed: Record<string, string> = {};
  for (const row of rows) {
    const draft = drafts[row.id];
    if (draft !== undefined && draft !== valueText(row.value, row.type)) changed[row.id] = draft;
  }
  return changed;
}
