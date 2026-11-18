// The scope's readout: what needs the owner comes first and opens Tasks,
// `nothing` when no task waits, and every value is marked `(last known)`
// while the server isn't answering.
import { expect, it } from "vitest";
import type { TaskInfo, TasksPayload } from "../../../src/api";
import { initialState } from "../../../src/state";
import type { AppState, Connection } from "../../../src/state";
import { buildReadout, LAST_KNOWN } from "../../../src/views/scope";
import { serverState } from "../../state/serverFixture";

const NOW = Date.parse("2026-11-17T12:00:00Z");
const OFFLINE: Connection = { status: "offline", retryAt: NOW, since: NOW };

const task = (id: string, status: TaskInfo["status"], you = ""): TaskInfo => ({
  id,
  name: `Task ${id}`,
  pct: 50,
  status,
  number: 0,
  next: "",
  you,
  updatedAt: "2026-11-17T11:00:00Z",
});

function tasksOf(...active: TaskInfo[]): TasksPayload {
  const needsYou = active.filter((one) => one.status === "needs_you").length;
  return { updatedAt: null, active, queued: [], done: [], needsYou, overallPct: null, usage: null };
}

const ONLINE: AppState = {
  ...initialState,
  connection: { status: "online" },
  server: serverState(),
};

// [case, state, the first row as [label, value, view], whether every value ends in LAST_KNOWN]
const CASES: [string, AppState, [string, string, string], boolean][] = [
  [
    "needs you first",
    {
      ...ONLINE,
      tasks: tasksOf(task("a", "building"), task("b", "needs_you", "say yes to the hook")),
    },
    ["NEEDS YOU", "say yes to the hook", "tasks"],
    false,
  ],
  [
    "nothing waiting",
    { ...ONLINE, tasks: tasksOf(task("a", "review")) },
    ["NEEDS YOU", "nothing", "tasks"],
    false,
  ],
  [
    "offline",
    { ...ONLINE, connection: OFFLINE },
    ["NEEDS YOU", `nothing${LAST_KNOWN}`, "tasks"],
    true,
  ],
];

// Regression: offline, a busy turn's clock kept counting beside `(last known)`.
it("stops CLAUDE's turn clock at the drop while offline", () => {
  const server = serverState();
  server.orchestrator.turn = {
    ...server.orchestrator.turn,
    state: "working",
    startedAt: NOW - 42_000,
  };
  const state: AppState = { ...ONLINE, server, connection: OFFLINE };
  const claude = buildReadout(state, NOW + 60_000).find((row) => row.label === "CLAUDE");
  expect(claude?.value).toBe(`working 0:42 (main)${LAST_KNOWN}`);
});

it.each(CASES)("words the readout: %s", (_name, state, first, isStale) => {
  const rows = buildReadout(state, NOW);
  expect([rows[0].label, rows[0].value, rows[0].view]).toEqual(first);
  expect(rows.map((row) => row.label)).toEqual([
    "NEEDS YOU",
    "CHAT",
    "CLAUDE",
    "VOICE",
    "BOARD",
    "YOU",
  ]);
  expect(rows.every((row) => row.value.endsWith(LAST_KNOWN))).toBe(isStale);
});
