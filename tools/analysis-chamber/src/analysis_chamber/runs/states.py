"""A run's phase and status words, and the order the phases run in."""

from enum import StrEnum


class Phase(StrEnum):
    """The step a run is on. A run moves through PHASE_ORDER once."""

    PLAN = "plan"
    COLLECT = "collect"
    ANALYSE = "analyse"
    CRITIQUE = "critique"
    REPORT = "report"


PHASE_ORDER: tuple[Phase, ...] = (
    Phase.PLAN,
    Phase.COLLECT,
    Phase.ANALYSE,
    Phase.CRITIQUE,
    Phase.REPORT,
)


class Status(StrEnum):
    """Where a run stands. Shown to the user as these words, never as a colour."""

    AWAITING_APPROVAL = "awaiting_approval"
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
