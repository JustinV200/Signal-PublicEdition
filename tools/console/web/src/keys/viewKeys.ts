// Which view each Ctrl+digit opens. Ctrl+1 to Ctrl+6 follow the six tabs;
// Ctrl+7 and Ctrl+8 opened Models and Tools before those moved into System,
// so they stay aliases for System; Ctrl+9 opens Setup, tab or no tab.
import type { View } from "../state";

const VIEW_BY_DIGIT: Readonly<Record<string, View>> = {
  "1": "scope",
  "2": "chat",
  "3": "voice",
  "4": "boards",
  "5": "tasks",
  "6": "system",
  "7": "system",
  "8": "system",
  "9": "setup",
};

/**
 * The view Ctrl+`key` opens.
 *
 * @param key A KeyboardEvent's `key`, e.g. "6".
 * @returns The view, or undefined for a key that opens none.
 */
export function viewForDigit(key: string): View | undefined {
  return Object.hasOwn(VIEW_BY_DIGIT, key) ? VIEW_BY_DIGIT[key] : undefined;
}
