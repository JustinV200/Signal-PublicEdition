"""Shortens text for one-line listings, dialogs and spoken notifications.

Shared by the repos listing (first prompts), the approvals dialog (tool
details), the voice notifications (final replies) and session status.
"""

import re

ELLIPSIS = "…"

# A sentence ends at ., ! or ? followed by whitespace. Good enough for spoken
# summaries; abbreviations like "e.g." only make a summary one sentence short.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def truncate(text: str, max_chars: int) -> str:
    """Collapse whitespace and cut text to max_chars, marking the cut with an ellipsis.

    Args:
        text: Any text.
        max_chars: The longest result allowed, ellipsis included. Must be >= 1.

    Returns:
        The single-line, possibly shortened text.
    """
    single_line = " ".join(text.split())
    if len(single_line) <= max_chars:
        return single_line
    return single_line[: max_chars - len(ELLIPSIS)].rstrip() + ELLIPSIS


def first_sentences(text: str, count: int, max_chars: int) -> str:
    """The first `count` sentences of text, on one line, capped at max_chars.

    Args:
        text: Prose, possibly multi-line.
        count: How many sentences to keep.
        max_chars: Hard cap on the result, applied after picking sentences.

    Returns:
        The shortened text ("" for blank input).
    """
    single_line = " ".join(text.split())
    sentences = _SENTENCE_END.split(single_line)
    return truncate(" ".join(sentences[:count]), max_chars)
