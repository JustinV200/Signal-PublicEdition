"""When the dialog's Allow button may take effect.

Allow only counts once the window has been on screen for the arm delay, so a
click aimed at another window just as the dialog pops up can't approve. Pure
logic, kept apart from tkinter so it can be tested without a window.
"""


def is_armed(shown_at_s: float | None, now_s: float, arm_delay_s: float) -> bool:
    """Say whether Allow may take effect now.

    Args:
        shown_at_s: Monotonic time the window first appeared, or None if it
            hasn't appeared yet.
        now_s: The current monotonic time.
        arm_delay_s: Seconds the window must have been shown first.

    Returns:
        True only when the window has been shown for at least `arm_delay_s`.
    """
    if shown_at_s is None:
        return False
    return now_s - shown_at_s >= arm_delay_s
