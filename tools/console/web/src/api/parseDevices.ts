// Shape checks for GET /api/devices and the POST /api/away reply. A row
// without an id or name is dropped; an unknown state reads as `unknown`.
import { dictList, isDict, stringOr } from "./parseFields";
import type { AwayInfo, AwayState, DeviceState, DevicesPayload } from "./types";

const DEVICE_STATES: readonly DeviceState[] = ["on", "off", "unknown"];
const AWAY_STATES: readonly AwayState[] = ["here", "away", "asleep"];

/** Checks the away block; null when it is missing or unreadable. */
export function parseAway(value: unknown): AwayInfo | null {
  if (!isDict(value)) return null;
  const state = AWAY_STATES.find((name) => name === value.state);
  if (!state) return null;
  return { state, endsAt: stringOr(value.endsAt, null), note: stringOr(value.note, "") };
}

/** Checks a GET /api/devices body. */
export function parseDevicesPayload(value: unknown): DevicesPayload {
  const dict = isDict(value) ? value : {};
  const devices = dictList(dict.devices)
    .filter((row) => typeof row.id === "string" && typeof row.name === "string")
    .map((row) => ({
      id: row.id as string,
      name: row.name as string,
      state: DEVICE_STATES.find((name) => name === row.state) ?? "unknown",
      words: stringOr(row.words, ""),
      canOpen: row.canOpen === true,
    }));
  return { devices, away: parseAway(dict.away) };
}
