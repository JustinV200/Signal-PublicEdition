"""ensure_not_stricter: the re-check right before a click refuses anything that asks more."""

import pytest

from browser_tool.actions import ActionError
from browser_tool.actions.gating import ensure_not_stricter
from browser_tool.config import ALL_CATEGORIES, CATEGORY_PATTERNS
from browser_tool.gates import ConfirmRules

RULES = ConfirmRules(CATEGORY_PATTERNS, ALL_CATEGORIES)
LOG_ONLY = RULES.check(None, "the element is in a frame with an unverified origin")


def _check(text):
    """The text rules' verdict on one label (None for no label)."""
    return RULES.check_texts([text]) if text is not None else None


@pytest.mark.parametrize(
    ("checked", "now", "is_refused"),
    [
        (None, "Send", True),  # nothing asked, now it asks
        ("Send", "Delete", True),  # another reason
        ("Send", "Send and delete", True),  # same first reason, one more category
        ("Send", "Send", False),
        ("Send", "Edit", False),  # now nothing matches
    ],
)
def test_a_recheck_refuses_only_what_asks_more(checked, now, is_refused):
    if is_refused:
        with pytest.raises(ActionError, match="changed after it was checked"):
            ensure_not_stricter(_check(checked), _check(now))
    else:
        ensure_not_stricter(_check(checked), _check(now))


def test_a_recheck_allows_a_log_only_verdict():
    ensure_not_stricter(None, LOG_ONLY)
