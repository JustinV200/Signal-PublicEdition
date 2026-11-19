// The radar's blips: an ordinary task's range is its progress (rim 0%, just
// outside Claude's mark at 100%); the tasks that need the owner are one
// triangle whose count shows whole, clear of everything else on the face, and
// none of them takes a place among the others; and a stream with no byte for
// 25 s reads `NO SIGNAL 25s` (which also stops the sweep).
import { expect, it } from "vitest";
import type { TaskInfo } from "../../../src/api";
import { initialState } from "../../../src/state";
import type { AppState } from "../../../src/state";
import { buildBlips, signalWords } from "../../../src/views/scope";
import { boxOf, layoutLabels, polar, ringCaptions } from "../../../src/views/scope/radar";
import type { Blip } from "../../../src/views/scope/radar";
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

// [case, active tasks (the one checked has id `t`), the last byte, [shape, range], the signal words]
const CASES: [string, TaskInfo[], number, [string, number], string | null][] = [
  ["0% on the rim", [task(0, "building")], FRESH, ["half", 1], null],
  ["100% by the centre", [task(100, "review")], FRESH, ["half", 0.1], null],
  ["stale stream", [task(50, "building")], STALE, ["half", 0.55], "NO SIGNAL 25s"],
];

it.each(CASES)("plots the radar: %s", (_name, active, syncedAt, [shape, range], signal) => {
  const state = stateWith(active, syncedAt);
  const blip = buildBlips(state, NOW).find((each) => each.id === "task-t");
  expect(blip?.shape).toBe(shape);
  expect(blip?.range).toBeCloseTo(range);
  expect(signalWords(state.syncedAt, false, NOW)).toBe(signal);
});

// The ordinary tasks that come nearest the count: out by the rim where its
// mark is (of three, one sits on the very edge of the gap round its line), and
// round the centre where its label ends (95% on that edge is the nearest a mark
// gets to it).
const ORDINARY_PCTS = {
  "three on the rim": [0, 0, 0],
  "many by the centre": Array.from({ length: 39 }, (_, index) => (index % 2 ? 95 : 100)),
};

// [tasks that need the owner, the ordinary tasks, the count's label (null: no count drawn)]
const COUNTS: [number, keyof typeof ORDINARY_PCTS, string | null][] = [
  [0, "three on the rim", null],
  [1, "three on the rim", "1 NEEDS YOU"],
  [3, "many by the centre", "3 NEED YOU"],
  [19, "many by the centre", "19 NEED YOU"],
  [200, "many by the centre", "200 NEED YOU"],
];

type Box = ReturnType<typeof boxOf>;
const overlaps = (a: Box, b: Box) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
// A mark is 11 units wide; the layout keeps a box of 12 for it.
const MARK_HALF = 6;
function markBox(blip: Blip): Box {
  const { x, y } = polar(blip.bearingDeg, blip.range);
  return { x0: x - MARK_HALF, x1: x + MARK_HALF, y0: y - MARK_HALF, y1: y + MARK_HALF };
}

const COUNTS_NAME = "counts %i needs-you tasks in one triangle, whole and clear (%s)";
it.each(COUNTS)(COUNTS_NAME, (count, ordinaryPcts, label) => {
  const ordinary = ORDINARY_PCTS[ordinaryPcts].map((pct, index) =>
    task(pct, "building", `o${index}`),
  );
  const waiting = Array.from({ length: count }, (_, index) => task(100, "needs_you", `w${index}`));
  const blips = buildBlips(stateWith([...waiting, ...ordinary], FRESH), NOW);
  const urgent = blips.filter((blip) => blip.isUrgent);
  const others = blips.filter((blip) => !blip.isUrgent);

  expect(urgent.map((blip) => [blip.shape, blip.label, blip.view])).toEqual(
    label ? [["triangle", label, "tasks"]] : [],
  );
  // No waiting task is drawn or takes a slot: the rest is the face with nobody waiting.
  expect(others).toEqual(buildBlips(stateWith(ordinary, FRESH), NOW));

  const captions = ringCaptions().map(boxOf);
  const labels = layoutLabels(blips, captions);
  const otherLabels = others.flatMap((blip) => {
    const placed = labels.get(blip.id);
    return placed ? [boxOf(placed)] : [];
  });
  const rest = [...captions, ...others.map(markBox), ...otherLabels];
  urgent.forEach((blip) => {
    const placed = labels.get(blip.id);
    expect(placed?.text).toBe(label);
    const own = [markBox(blip), boxOf(placed!)];
    expect(rest.filter((box) => own.some((mine) => overlaps(mine, box)))).toEqual([]);
  });
});
