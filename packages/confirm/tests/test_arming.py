"""Allow only takes effect once the window has been on screen for the arm delay."""

from signal_confirm.arming import is_armed


def test_allow_is_armed_only_after_the_window_has_been_shown_for_the_delay():
    assert not is_armed(None, now_s=100.0, arm_delay_s=1.5)
    assert not is_armed(100.0, now_s=101.4, arm_delay_s=1.5)
    assert is_armed(100.0, now_s=101.5, arm_delay_s=1.5)
