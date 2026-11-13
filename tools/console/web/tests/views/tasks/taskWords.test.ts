// The Tasks page words: a status is always its number and a word, and a
// usage window that has reset reads as unknown instead of an old percentage.
import { describe, expect, it } from "vitest";
import type { TaskInfo, UsageInfo } from "../../../src/api";
import { statusTag, usageWords } from "../../../src/views/tasks";

const NOW = Date.parse("2026-10-20T12:00:00Z");

describe("tasks words", () => {
  it("tags a status with its number and word", () => {
    const task = { number: 3, status: "needs_you" } as TaskInfo;
    expect(statusTag(task)).toBe("[3 needs you]");
  });

  it("shows a window past its reset as -- and says how old the numbers are", () => {
    const usage: UsageInfo = {
      fiveHour: { usedPct: 42.4, resetsAt: "2026-10-20T11:59:00Z" },
      sevenDay: { usedPct: 18, resetsAt: "2026-10-24T00:00:00Z" },
      agents: 5,
      updatedAt: "2026-10-20T11:58:00Z",
    };
    expect(usageWords(usage, NOW)).toBe("5h -- · wk 18% · agents 5 · as of 2m ago");
    expect(usageWords(null, NOW)).toBe("usage unknown");
  });
});
