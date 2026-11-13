"""Tests for the keeper's night guard: the projector's black window follows the night view."""

import threading
from concurrent.futures import Future

from sleepmode.keeper.night_guard import NIGHT_RETRY_S, NightGuard, NightView

PROJECTOR = (1920, 0, 1920, 1080)


class FakeCover:
    """Stands in for BlackoutWindows over the projector; `opened` lists every one."""

    opened: list["FakeCover"] = []

    def __init__(self, rects: list) -> None:
        assert rects == [PROJECTOR]
        FakeCover.opened.append(self)
        self.is_open = True

    def close(self) -> None:
        self.is_open = False


def _inline(check) -> Future:
    future: Future = Future()
    future.set_result(check())
    return future


def test_the_cover_comes_off_once_the_whiteboard_is_up_and_back_if_it_goes() -> None:
    # Regression: a whiteboard down at sleep time left the projector black all night,
    # and one that stopped mid-night left the desktop lit on it.
    FakeCover.opened = []
    clock, showing, shows = [0.0], [False], []

    def show() -> None:
        shows.append(clock[0])
        if clock[0] < NIGHT_RETRY_S:
            raise OSError("the whiteboard daemon isn't running")
        showing[0] = True

    guard = NightGuard(
        PROJECTOR, NightView(lambda: showing[0], show), FakeCover, _inline, lambda: clock[0]
    )

    def poll_at(at: float) -> bool:
        """Poll twice (start the check, then act on it); True if the projector is covered."""
        clock[0] = at
        guard.poll()
        guard.poll()
        return any(cover.is_open for cover in FakeCover.opened)

    assert poll_at(0.0) and shows == [0.0]  # down at sleep time: stays covered
    assert poll_at(30.0) and shows == [0.0]  # not retried before NIGHT_RETRY_S
    assert not poll_at(60.0) and shows == [0.0, 60.0]  # it started: the sky shows
    showing[0] = False  # the daemon stopped mid-night
    assert poll_at(120.0) and shows == [0.0, 60.0]  # covered at once, no show yet
    assert not poll_at(180.0) and shows == [0.0, 60.0, 180.0]
    assert len(FakeCover.opened) == 2


def test_close_waits_for_a_show_in_flight() -> None:
    # Regression: a show still running when the keeper exited landed after the wake's
    # hide and left the whiteboard in its night view.
    FakeCover.opened = []
    release, shows = threading.Event(), []

    def show() -> None:
        release.wait()
        shows.append(True)

    guard = NightGuard(PROJECTOR, NightView(lambda: False, show), FakeCover, clock=lambda: 0.0)
    guard.poll()  # starts the check on its own thread
    threading.Timer(0.05, release.set).start()
    guard.close()
    assert shows == [True]
