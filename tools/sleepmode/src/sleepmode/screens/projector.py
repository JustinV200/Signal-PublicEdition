"""split_projector: which display is the projector (kept on) and which displays get darkened."""

import logging
from collections.abc import Sequence

from signal_displays import Monitor, ProjectorNotFoundError, pick_projector

log = logging.getLogger(__name__)


def split_projector(
    monitors: Sequence[Monitor], name_match: str
) -> tuple[Monitor | None, list[Monitor]]:
    """Separate the projector from the other displays, by the whiteboard's own rule.

    The projector is the display whose friendly or device name contains `name_match`,
    else the first non-primary display (signal_displays.pick_projector).

    Args:
        monitors: Every attached display.
        name_match: The projector's name match (sleepmode.config.projector_match).

    Returns:
        (projector or None, every other display). With a single display there's no
        projector, and that display is darkened.
    """
    try:
        projector = pick_projector(list(monitors), name_match)
    except ProjectorNotFoundError as error:
        log.info("no projector: %s", error)
        return None, list(monitors)
    others = [monitor for monitor in monitors if monitor.device_name != projector.device_name]
    return projector, others
