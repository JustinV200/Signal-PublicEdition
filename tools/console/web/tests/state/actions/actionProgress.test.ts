// A button's run is read off its delivery: sending, working (the server runs
// it), done or failed. The pending set drops a settled or stale row and never
// pends a replayed one.
import { describe, expect, it } from "vitest";
import { actionProgress, PENDING_MAX_MS, pendingActions, pendingRows } from "../../../src/state";
import type { LocalMessage } from "../../../src/state";

const NOW = 1_000_000;

function actionRow(partial: Partial<LocalMessage> = {}): LocalMessage {
  return {
    id: "a1",
    role: "you",
    kind: "action",
    text: "Start voice",
    at: NOW - 1000,
    delivery: "running",
    origin: { kind: "action", action: "voice.start" },
    ...partial,
  };
}

describe("actionProgress", () => {
  it("goes sending, working, then done or failed, pending only until it settles", () => {
    expect(actionProgress(actionRow({ delivery: "sending" }))).toBe("sending");
    expect(actionProgress(actionRow())).toBe("working");
    expect(pendingActions([actionRow()], NOW)).toEqual(new Set(["voice.start"]));

    for (const delivery of ["done", "failed"] as const) {
      const settled = actionRow({ delivery });
      expect(actionProgress(settled)).toBe(delivery);
      expect(pendingActions([settled], NOW).size).toBe(0);
    }
  });

  it("lifts a stale pending after PENDING_MAX_MS and never pends a replayed row", () => {
    const stale = actionRow({ at: NOW - PENDING_MAX_MS });
    const replayed = actionRow({ id: "a2", origin: undefined });
    expect(pendingActions([stale, replayed], NOW).size).toBe(0);
    expect(pendingRows([stale, replayed], NOW)).toEqual([]);
    expect(pendingRows([actionRow()], NOW).map((row) => row.id)).toEqual(["a1"]);
  });
});
