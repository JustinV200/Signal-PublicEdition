// The Tasks page words and order: a status is always a word (and `!` for one
// that needs the owner), a usage window that has reset reads as unknown
// instead of an old percentage, and tasks waiting on the owner come first.
import { describe, expect, it } from "vitest";
import type { TaskInfo, UsageInfo } from "../../../src/api";
import { needsYouFirst, statusTag, usageWords } from "../../../src/views/tasks";

const NOW = Date.parse("2026-10-20T12:00:00Z");

describe("tasks words", () => {
  it.each([
    ["needs_you", "! [needs you]"],
    ["review", "[review]"],
  ] as const)("tags %s by word, without the status number", (status, tag) => {
    expect(statusTag({ number: 3, status } as TaskInfo)).toBe(tag);
  });

  it("labels the usage line, shows a window past its reset as -- and says how old it is", () => {
    const usage: UsageInfo = {
      fiveHour: { usedPct: 42.4, resetsAt: "2026-10-20T11:59:00Z" },
      sevenDay: { usedPct: 18, resetsAt: "2026-10-24T00:00:00Z" },
      agents: 5,
      updatedAt: "2026-10-20T11:58:00Z",
    };
    expect(usageWords(usage, NOW)).toBe(
      "Claude usage: 5-hour window -- · week 18% · 5 agents · updated 2m ago",
    );
    expect(usageWords(null, NOW)).toBe("Claude usage: unknown");
  });
});

describe("tasks order", () => {
  it("lifts needs-you tasks to the top whatever their percent, keeping the rest in order", () => {
    const task = (id: string, pct: number, status: TaskInfo["status"]) =>
      ({ id, pct, status }) as TaskInfo;
    const active = [
      task("a", 90, "review"),
      task("b", 60, "needs_you"),
      task("c", 40, "building"),
      task("d", 10, "needs_you"),
    ];
    expect(needsYouFirst(active).map((t) => t.id)).toEqual(["b", "d", "a", "c"]);
  });
});
