"""MouseTravel: tells a deliberate mouse move from an optical mouse's jitter.

An optical mouse left alone can twitch the cursor a few pixels now and then, which
used to wake sleep mode in the night. A move counts as deliberate once the cursor's
recent positions span at least mouse_move_px across or down within mouse_move_window_s
(sleepmode.config.InputSettings). A span, not a path length, so jitter that wobbles
back and forth never adds up, while a shake of the mouse still covers it at once.
sleepmode.keeper.input_watch feeds it each move the hooks see.
"""

from collections import deque

from sleepmode.config import InputSettings


class MouseTravel:
    """The cursor's positions over the last window, and whether they span enough."""

    def __init__(self, settings: InputSettings) -> None:
        """Start with no positions.

        Args:
            settings: The span in pixels and the window in seconds.
        """
        self._settings = settings
        self._points: deque[tuple[float, int, int]] = deque()  # (seconds, x, y), oldest first

    def is_deliberate(self, now: float, x: int, y: int) -> bool:
        """Record a move and say whether the cursor has now travelled far enough.

        Args:
            now: Monotonic seconds of the move.
            x: The cursor's new screen x.
            y: The cursor's new screen y.

        Returns:
            True when the positions within the window span at least mouse_move_px.
        """
        window_s = self._settings.mouse_move_window_s
        while self._points and now - self._points[0][0] > window_s:
            self._points.popleft()
        # A fast mouse reports far more often than the cursor changes pixel; keeping only
        # new positions keeps this short enough to scan inside the hook.
        if not self._points or self._points[-1][1:] != (x, y):
            self._points.append((now, x, y))
        xs = [point[1] for point in self._points]
        ys = [point[2] for point in self._points]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        return span >= self._settings.mouse_move_px
