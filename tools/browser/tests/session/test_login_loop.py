"""The login-loop guard: fills counted per site, pure, with a fake clock."""

import pytest
from support.fake_duo import FakeClock

from browser_tool.session import LOOP_WINDOW_S, LoginLoopGuard

SITE = "cas.example.edu"
OTHER_SITE = "accounts.example.com"


@pytest.mark.parametrize(
    ("fills", "check_at", "is_refused", "is_other_refused"),
    [
        ([(SITE, 0)], 10, False, False),
        # A login plus one retry is fine; a third fill is refused.
        ([(SITE, 0), (SITE, 30)], 40, True, False),
        # Fills on another site don't count toward this one.
        ([(SITE, 0), (OTHER_SITE, 10), (OTHER_SITE, 20)], 30, False, True),
        # The window resets: the first fill is over 10 minutes old by then.
        ([(SITE, 0), (SITE, 30)], LOOP_WINDOW_S + 1, False, False),
    ],
    ids=["one-fill", "two-fills", "per-site", "window-resets"],
)
def test_a_third_fill_on_a_site_within_the_window_is_refused(
    fills, check_at, is_refused, is_other_refused
):
    clock = FakeClock()
    guard = LoginLoopGuard(clock)
    for site, at in fills:
        clock.now = at
        guard.note_fill(site)
    clock.now = check_at
    assert guard.is_loop(SITE) is is_refused
    assert guard.is_loop(OTHER_SITE) is is_other_refused
