"""DarkRoom: tells the change watcher and the drift monitor when the room is too dark.

In a dark room a blank-page photo is nearly black (median grey under 10 on the
owner's webcam): the ink can't be read and the board's outline can't be found, so
every clean capture and timed check is only a flash. The projected page is mostly
black, so the live camera frame's median grey is about the room light alone, and
it's known before anything is blanked. That assumes the board covers well under
half the frame (about 30% now), so the median is the room around it. If the camera
is reframed tighter onto the board, a bright projected page can lift the median
over dark_floor in a dark room and let flashes through. The watcher owns one
DarkRoom and the drift monitor asks the same one, so the state (and its log line)
is shared.
"""

import logging

import numpy as np

from whiteboard.camera.clean_capture import FrameSource

logger = logging.getLogger(__name__)

# Grey levels over the floor a dark room must reach to count as light again, so a
# room right at the floor doesn't flip (and log) every sample.
DARK_HYSTERESIS = 5.0
# Every this-many px in each direction: plenty for a median, and cheap.
SAMPLE_STEP_PX = 8


class DarkRoom:
    """Judges the room's light from the live frame; logs once each time it goes dark or light."""

    def __init__(self, camera: FrameSource, floor: float) -> None:
        """Args:
        camera: The live frame source.
        floor: Median grey (0-255) under which the room is dark ([watcher] dark_floor).
        """
        self._camera = camera
        self._floor = floor
        self._is_dark = False

    def is_dark(self) -> bool:
        """Whether the room is dark now. With no recent frame, the last answer stands."""
        frame = self._camera.latest()
        if frame is None:
            return self._is_dark
        # The median over all three colour channels is close enough to the grey one.
        brightness = float(np.median(frame[::SAMPLE_STEP_PX, ::SAMPLE_STEP_PX]))
        floor = self._floor + (DARK_HYSTERESIS if self._is_dark else 0.0)
        is_dark = brightness < floor
        if is_dark != self._is_dark:
            self._is_dark = is_dark
            state = "too dark to read the board; no clean captures or timed checks"
            logger.info(
                "room %s (median grey %.0f)", state if is_dark else "light again", brightness
            )
        return is_dark
