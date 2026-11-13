"""Public API of signal_displays: list the attached monitors and pick the projector."""

from signal_displays.friendly_names import friendly_names
from signal_displays.monitors import (
    Monitor,
    ProjectorNotFoundError,
    find_projector,
    list_monitors,
    pick_projector,
)

__all__ = [
    "Monitor",
    "ProjectorNotFoundError",
    "find_projector",
    "friendly_names",
    "list_monitors",
    "pick_projector",
]
