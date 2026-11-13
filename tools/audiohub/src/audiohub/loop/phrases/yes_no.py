"""Yes and no words, for telling the user's reply from an echo of Claude.

Claude may end a reply with a question ("Shall I delete the old logs?"), and
the user answers in its words ("Yes, delete the old logs."). echo.py uses
`is_yes_or_no_word` so a leading yes or no that Claude didn't say right there
always marks the transcript as the user's reply, not Claude's echo.
"""

_YES_WORDS = frozenset(
    {
        "yes", "yeah", "yep", "yup", "yea", "aye", "sure", "ok", "okay", "alright",
        "affirmative", "absolutely", "definitely", "certainly", "correct", "allow",
        "approve", "approved", "fine",
    }
)  # fmt: skip
_NO_WORDS = frozenset(
    {"no", "nope", "nah", "dont", "deny", "denied", "negative", "never", "not", "cancel", "stop"}
)


def is_yes_or_no_word(word: str) -> bool:
    """Say whether a normalised word (as `tokens.words` gives it) is a yes or a no on its own.

    Args:
        word: One lowercase word without punctuation.

    Returns:
        True for a yes-word or a no-word.
    """
    return word in _YES_WORDS or word in _NO_WORDS
