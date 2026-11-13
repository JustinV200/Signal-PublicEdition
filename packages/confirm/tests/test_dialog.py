"""The real dialog, end to end. Opt-in: run with `uv run pytest -m desktop`."""

import time

import pytest

from signal_confirm import confirm
from signal_confirm.launcher import CHILD_START_GRACE_S


@pytest.mark.desktop
def test_real_dialog_denies_itself_after_the_timeout():
    started = time.monotonic()
    assert confirm("signal_confirm test", "This denies itself in 1 second.", timeout_s=1) is False
    # Denied by the dialog's own timer, not by the parent killing a hung child.
    assert time.monotonic() - started < CHILD_START_GRACE_S
