"""Decide whether an element's text matches a list of sensitive-action patterns.

ConfirmRules (confirm_rules.py) keeps one ActionRules per [gates] always_confirm
category; the patterns come from browser_tool.config.CATEGORY_PATTERNS and the
owner's [gates] patterns. Matching is case-insensitive against the accessible
name and the live element text.
"""

import re
from collections.abc import Sequence


class ActionRules:
    """Compiled sensitive-action patterns."""

    def __init__(self, patterns: Sequence[str]):
        """Compile the patterns.

        Raises:
            re.error: If a pattern is not a valid regex (config validates this first).
        """
        self._patterns = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    def find_match(self, texts: Sequence[str]) -> str | None:
        """Return the first pattern that matches any of `texts`, or None.

        Args:
            texts: Candidate texts, e.g. the accessible name and the element's text.
        """
        for pattern in self._patterns:
            if any(pattern.search(text) for text in texts if text):
                return pattern.pattern
        return None
