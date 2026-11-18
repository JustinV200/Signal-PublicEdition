"""MonitorResult: what sleep mode did to one display, as stored in the state file and reported."""

from dataclasses import dataclass

# How a display was darkened.
DDC_OFF = "ddc-off"  # powered off over DDC/CI (VCP 0xD6)
BLACK_WINDOW = "black-window"  # covered by a borderless, topmost black window
NIGHT_SKY = "night-sky"  # the projector shows the whiteboard's night view
METHODS: tuple[str, ...] = (DDC_OFF, BLACK_WINDOW, NIGHT_SKY)
# Old methods a state file may still hold, and what they read as now. The black page was
# the night view without the sky, so it's the night view (wake hides it).
# TODO: drop it once no sleepmode MCP server started before the black-page option went
# (2026-11-18) can still be running (after a wake and an MCP restart).
LEGACY_METHODS: dict[str, str] = {"black-page": NIGHT_SKY}


@dataclass(frozen=True)
class MonitorResult:
    """One display's outcome.

    Attributes:
        device_name: e.g. `\\\\.\\DISPLAY5`.
        friendly_name: The EDID name, e.g. "PROJ-1"; "" if unknown.
        method: One of METHODS.
        detail: Why this method (e.g. the DDC error that forced a black window); "" if none.
        rect: The display's physical bounds (x, y, width, height), for black windows.
        is_projector: True for the projector.
    """

    device_name: str
    friendly_name: str
    method: str
    detail: str
    rect: tuple[int, int, int, int]
    is_projector: bool = False

    @property
    def label(self) -> str:
        """A readable name: the friendly name with the device name, or just the device name."""
        if self.friendly_name:
            return f"{self.friendly_name} ({self.device_name})"
        return self.device_name
