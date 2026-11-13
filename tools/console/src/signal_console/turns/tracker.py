"""`TurnTracker`: whether the claimed orchestrator is working, from its turn hooks' reports.

The turn hook (hooks/turn.py) reports `start` (UserPromptSubmit), `end` (Stop,
StopFailure) and `idle` (Notification idle_prompt). Each carries `at`, stamped
when the hook process started. Async hooks can land out of order, so on a short
turn the start can even be stamped after the end. The rules, which fail safe
towards idle (the next hook corrects any mistake):

- a start and an end stamped within FOLD_S of each other belong to the same
  turn: a start that late after the last end is ignored, and an end that early
  before the open start still closes it;
- `idle` ends the open turn only when it is stamped IDLE_MIN_AGE_S after the
  turn's start (a late idle_prompt from the previous turn can't end an inbox turn);
- interrupts fire no hook, so an open turn with no activity for STALE_AFTER_S
  reads as `stale`.

Pure logic: callers pass the clock and the agent count, so tests drive it directly.
"""

from dataclasses import dataclass
from typing import Any, Literal

TurnPhase = Literal["start", "end", "idle"]
TURN_PHASES: frozenset[str] = frozenset({"start", "end", "idle"})

FOLD_S = 2.0
IDLE_MIN_AGE_S = 60.0
STALE_AFTER_S = 10 * 60.0
MS_PER_S = 1000


@dataclass(frozen=True)
class TurnReport:
    """One turn hook report.

    Attributes:
        phase: start, end or idle.
        session_id: The claimed session's id, as the hook saw it.
        at: Epoch seconds when the hook process started.
        background_tasks: How many background tasks the Stop input listed (end only), else None.
        effort: The effort level the Stop input carried (end only), else None.
    """

    phase: TurnPhase
    session_id: str
    at: float
    background_tasks: int | None = None
    effort: str | None = None


class TurnTracker:
    """Folds turn hook reports into a state: working, agents, idle, stale or unknown."""

    def __init__(self) -> None:
        """Start knowing nothing: `unknown` until the first report."""
        self.reset()

    def reset(self) -> None:
        """Forget everything (the claim moved to another session)."""
        self._session_id: str | None = None
        self._open_since: float | None = None
        self._last_end: float | None = None
        self._last_activity: float | None = None
        self._background_tasks: int | None = None
        self._effort: str | None = None

    @property
    def session_id(self) -> str | None:
        """The claimed session's id from its latest report, or None before any."""
        return self._session_id

    @property
    def effort(self) -> str | None:
        """The effort level the session's latest Stop carried, or None before one did."""
        return self._effort

    def record(self, report: TurnReport) -> None:
        """Apply one hook report."""
        self._session_id = report.session_id
        self._effort = report.effort or self._effort
        self.note_activity(report.at)
        if report.phase == "start":
            self._start(report.at)
        elif report.phase == "end":
            self._end(report.at, report.background_tasks)
        elif self._open_since is not None and report.at - self._open_since >= IDLE_MIN_AGE_S:
            self._end(report.at, None)

    def note_activity(self, at: float) -> None:
        """Note other activity from the session (its subagent hooks), so a turn isn't stale."""
        if self._last_activity is None or at > self._last_activity:
            self._last_activity = at

    def status(self, now: float, usage_agents: int | None) -> dict[str, Any]:
        """The orchestrator's turn state for /api/state.

        Args:
            now: Epoch seconds.
            usage_agents: The session's running subagents in usage.json, or None if unknown.

        Returns:
            `{state, startedAt, lastActivityAt, agents, agentsUnsure}`; times are epoch ms.
            When usage.json and the last Stop's background tasks disagree, `agents`
            is the lower count and `agentsUnsure` is true.
        """
        agents, is_unsure = _agent_count(usage_agents, self._background_tasks)
        return {
            "state": self._state(now, agents),
            "startedAt": _ms(self._open_since),
            "lastActivityAt": _ms(self._last_activity),
            "agents": agents,
            "agentsUnsure": is_unsure,
        }

    def _state(self, now: float, agents: int | None) -> str:
        if self._last_activity is None:
            return "unknown"
        if self._open_since is not None:
            return "stale" if now - self._last_activity >= STALE_AFTER_S else "working"
        return "agents" if agents else "idle"

    def _start(self, at: float) -> None:
        # Stamped no later than FOLD_S after the last end: that end's own (late) start.
        if self._last_end is not None and at <= self._last_end + FOLD_S:
            return
        self._open_since = at
        self._background_tasks = None  # counted again at this turn's end

    def _end(self, at: float, background_tasks: int | None) -> None:
        # An end stamped well before the open start belongs to an earlier turn.
        if self._open_since is None or at >= self._open_since - FOLD_S:
            self._open_since = None
            self._background_tasks = background_tasks
        if self._last_end is None or at > self._last_end:
            self._last_end = at


def _agent_count(usage_agents: int | None, background_tasks: int | None) -> tuple[int | None, bool]:
    if usage_agents is None or background_tasks is None:
        return (usage_agents if usage_agents is not None else background_tasks), False
    return min(usage_agents, background_tasks), usage_agents != background_tasks


def _ms(seconds: float | None) -> int | None:
    return None if seconds is None else round(seconds * MS_PER_S)
