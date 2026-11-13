"""The contract every lighting backend meets: off and restore, each answering a LightingReport.

Backends (OpenRGB, Dynamic Lighting, vendor commands) find their devices at run
time. One with nothing to do logs why at INFO and answers an empty report. Raising
is allowed: the Lighting switch (switch.py) turns any error into a note. Each call
gets a StepGuard (step_guard.py), which Lighting abandons if the call overruns.
"""

from dataclasses import dataclass
from typing import Protocol

from sleepmode.lighting.step_guard import StepGuard


@dataclass(frozen=True)
class LightingReport:
    """What a lighting step did.

    Attributes:
        lines: What was done, one line each, for the sleep summary (e.g. "OpenRGB: 4 lights off").
        notes: Problems worth telling the owner, like SleepState.notes.
    """

    lines: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def plus(self, other: "LightingReport") -> "LightingReport":
        """This report followed by other's lines and notes."""
        return LightingReport(self.lines + other.lines, self.notes + other.notes)


class Backend(Protocol):
    """One way of reaching lights."""

    name: str

    def off(self, may_snapshot: bool, guard: StepGuard) -> LightingReport:
        """Turn this backend's lights off.

        Args:
            may_snapshot: False when this sleep replaces one that already turned the
                lights off, so a saved "before" look isn't overwritten with the dark one.
            guard: Checked before each device change: once it's abandoned, stop. A
                connection the step opens is registered with it, to be closed then.
        """
        ...

    def restore(self, guard: StepGuard) -> LightingReport:
        """Bring this backend's lights back to their daytime look.

        Args:
            guard: As for off.
        """
        ...
