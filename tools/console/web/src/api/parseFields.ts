// Small field checks shared by the payload parsers (parse.ts, parseTasks.ts,
// parseDevices.ts): every server value is untrusted until it passes one.

export type Dict = Record<string, unknown>;

export function isDict(value: unknown): value is Dict {
  return typeof value === "object" && value !== null;
}

/** A finite number, else null. */
export function numberOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** A string, else `fallback`. */
export function stringOr<T extends string | null>(value: unknown, fallback: T): string | T {
  return typeof value === "string" ? value : fallback;
}

export function isTime(value: unknown): value is string | number {
  return typeof value === "string" || typeof value === "number";
}

/** The dicts in `value` (anything else is dropped); [] when it is not an array. */
export function dictList(value: unknown): Dict[] {
  return Array.isArray(value) ? value.filter(isDict) : [];
}
