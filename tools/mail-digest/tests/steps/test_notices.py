"""Tests for mail_digest.steps.notices: the runner's own reminders, keyed to repeat on schedule."""

import pytest

from mail_digest.mailbox import SEARCH_FAILED, AccountProblem
from mail_digest.memory import Window, is_valid_key
from mail_digest.steps import gap_notices, signin_reminders

PROBLEMS = (
    AccountProblem("alt", "needs re-auth"),
    AccountProblem("school", "error"),
    AccountProblem("personal", "offline"),  # comes back by itself: logged only
    AccountProblem("work", SEARCH_FAILED),
)
WINDOWS = {
    "personal": Window(after=1_760_000_000, before=1_760_259_200),
    "alt": Window(after=1_760_000_000, before=1_760_259_200, skipped_since=1_759_000_000),
}


@pytest.mark.parametrize(
    ("notices", "keys"),
    [
        # Keyed per week folder name, so a reminder repeats at most weekly.
        (
            signin_reminders(PROBLEMS, "2026-10-19-to-10-25"),
            [
                "signin|alt|2026-10-19-to-10-25",
                "signin|school|2026-10-19-to-10-25",
                "search|work|2026-10-19-to-10-25",
            ],
        ),
        # Keyed per gap, so each skipped stretch is announced once.
        (gap_notices(WINDOWS), ["gap|alt|1759000000"]),
    ],
)
def test_runner_notices_cover_the_right_accounts_with_storable_keys(notices, keys):
    assert [n.key for n in notices] == keys
    # A key the state can't store would be spoken again on every run.
    assert all(is_valid_key(key) for key in keys)
