"""Sensitive-action pattern matching with every category's default patterns."""

import pytest

from browser_tool.config import CATEGORY_PATTERNS
from browser_tool.gates import ActionRules

RULES = ActionRules([pattern for patterns in CATEGORY_PATTERNS.values() for pattern in patterns])


@pytest.mark.parametrize(
    "text",
    [
        "Buy now for $42",
        "Pay $10",
        "Place your order",
        "Send message",
        "Submit Assignment",
        "Turn in",
        "Mark as done",
        "Unsubmit",
        "Share",
        "Upload file",
        "Merge pull request",
        "Commit changes",
        "Close issue",
        "Request edit access",
        "Unsubscribe",
        "Close as not planned",
        "Delete account",
        "Move to trash",
    ],
)
def test_sensitive_texts_match(text):
    assert RULES.find_match([text]) is not None


# Only purchases, sends and deletes ask: app access grants and consent words don't.
@pytest.mark.parametrize(
    "text",
    [
        "Show details",
        "PayPal info",
        "Sender name",
        "Allow",
        "Authorize MyApp",
        "Continue as the owner",
    ],
)
def test_lookalike_words_do_not_match(text):
    assert RULES.find_match([text]) is None
