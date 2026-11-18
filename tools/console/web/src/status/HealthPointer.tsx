// The status line's pointer to System: while one of the console's own checks
// (GET /api/health, read at sign-in, on opening System and on Refresh) isn't
// ok (the claim and whiteboard checks aside: the page words them live),
// a button names the first problem, `Console port: taken · see System`,
// and opens System, where the row has the fix. A failing check goes before
// one that only needs a look. Nothing shows while every check is ok or none
// was read; the mark repeats the words (a cross fails, a half disc needs a look).
import type { ConsoleCheck } from "../api";
import { useStore } from "../state";
import { Button, Mark } from "../ui";

// Checks the page already words live, so the pointer never repeats them: the
// claim is the connection words (`No Claude session`, `Claude session closed`),
// read from every state event, and the whiteboard is the Boards tab (`off`).
// Health is read only at load, on System and on Refresh, so a pointer for
// either would go stale (a claim made later would still read `none`) or show
// all day (the whiteboard is often off until Claude uses it).
const LIVE_ELSEWHERE = new Set(["claim", "whiteboard"]);

/** The first failing check, else the first that needs a look; null when all are ok. */
function firstProblem(checks: readonly ConsoleCheck[] | null): ConsoleCheck | null {
  const rows = (checks ?? []).filter((row) => !LIVE_ELSEWHERE.has(row.id));
  return rows.find((row) => row.level === "fail") ?? rows.find((row) => row.level !== "ok") ?? null;
}

/** The pointer, or nothing. */
export function HealthPointer() {
  const { state, dispatch } = useStore();
  const problem = firstProblem(state.health.checks);
  if (!problem) return null;
  return (
    <Button onClick={() => dispatch({ type: "view", view: "system" })}>
      <Mark shape={problem.level === "fail" ? "cross" : "half"} /> {problem.name}:{" "}
      {problem.state || "needs a look"} · see System
    </Button>
  );
}
