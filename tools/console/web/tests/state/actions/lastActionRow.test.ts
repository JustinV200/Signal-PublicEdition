// The result strip's row: the newest action this page sent once it has an
// outcome. Replayed rows (no local origin) never show, a done result clears
// after DONE_SHOW_MS, a failed one stays, and a newer action replaces it.
import { describe, expect, it } from "vitest";
import { DONE_SHOW_MS, lastActionRow } from "../../../src/state";
import type { LocalMessage } from "../../../src/state";

const NOW = 1_000_000;

function actionRow(id: string, partial: Partial<LocalMessage> = {}): LocalMessage {
  return {
    id,
    role: "you",
    kind: "action",
    text: 'Send to projector: "lecture"',
    at: NOW - 5000,
    delivery: "done",
    settledAt: NOW - 1000,
    origin: { kind: "action", action: "board.load", args: { name: "lecture" } },
    ...partial,
  };
}

describe("lastActionRow", () => {
  it.each([
    [
      "the newest local action wins",
      [actionRow("old", { delivery: "failed" }), actionRow("new")],
      "new",
    ],
    [
      "a replayed row is left out",
      [actionRow("local"), actionRow("replayed", { origin: undefined })],
      "local",
    ],
    ["a replay alone shows nothing", [actionRow("replayed", { origin: undefined })], null],
    ["a done result expires", [actionRow("a", { settledAt: NOW - DONE_SHOW_MS })], null],
    [
      "a failed result persists",
      [actionRow("a", { delivery: "failed", settledAt: NOW - 10 * DONE_SHOW_MS })],
      "a",
    ],
    [
      "a newer running action clears the last result",
      [actionRow("a"), actionRow("b", { delivery: "running" })],
      null,
    ],
  ])("%s", (_name, messages, expected) => {
    expect(lastActionRow(messages, NOW)?.id ?? null).toBe(expected);
  });
});
