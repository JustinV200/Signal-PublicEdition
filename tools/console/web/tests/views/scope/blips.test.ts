// The radar's blips: a task's range is its progress (rim 0%, just outside
// Claude's mark at 100%), a task that needs the owner is a triangle whose label
// shows in full (even as the middle of three, level with Claude), and a stream
// with no byte for 25 s reads `NO SIGNAL 25s` (which also stops the sweep).
import { expect, it } from "vitest";
import type { TaskInfo } from "../../../src/api";
import { initialState } from "../../../src/state";
import type { AppState } from "../../../src/state";
import { buildBlips, signalWords } from "../../../src/views/scope";
import { layoutLabels } from "../../../src/views/scope/radar";
import { serverState } from "../../state/serverFixture";

const NOW = Date.parse("2026-11-17T12:00:00Z");
const FRESH = NOW - 1000;
const STALE = NOW - 25_000;

const task = (pct: number, status: TaskInfo["status"], id = "t"): TaskInfo => ({
  id,
  name: "Brief phase 2",
  pct,
  status,
  number: 0,
  next: "",
  you: status === "needs_you" ? "say yes" : "",
  updatedAt: "2026-11-17T11:00:00Z",
});

function stateWith(active: TaskInfo[], syncedAt: number): AppState {
  const tasks = {
    updatedAt: null,
    active,
    queued: [],
    done: [],
    needsYou: 0,
    overallPct: null,
    usage: null,
  };
  return {
    ...initialState,
    connection: { status: "online" },
    server: serverState(),
    tasks,
    syncedAt,
  };
}

// [case, active tasks (the one checked has id `t`), the last byte, [shape, range],
//  its label as laid out (null: not checked), the signal words]
const CASES: [string, TaskInfo[], number, [string, number], string | null, string | null][] = [
  ["0% on the rim", [task(0, "building")], FRESH, ["half", 1], null, null],
  ["100% by the centre", [task(100, "review")], FRESH, ["half", 0.1], null, null],
  [
    "needs you: a triangle at 60%, its label whole",
    [task(80, "review", "a"), task(60, "needs_you"), task(20, "building", "b")],
    FRESH,
    ["triangle", 0.46],
    "Brief phase 2 60%",
    null,
  ],
  ["stale stream", [task(50, "building")], STALE, ["half", 0.55], null, "NO SIGNAL 25s"],
];

it.each(CASES)("plots the radar: %s", (_name, active, syncedAt, [shape, range], label, signal) => {
  const state = stateWith(active, syncedAt);
  const blips = buildBlips(state, NOW);
  const blip = blips.find((each) => each.id === "task-t");
  expect(blip?.shape).toBe(shape);
  expect(blip?.range).toBeCloseTo(range);
  if (label !== null) expect(layoutLabels(blips, []).get("task-t")?.text).toBe(label);
  expect(signalWords(state.syncedAt, false, NOW)).toBe(signal);
});
