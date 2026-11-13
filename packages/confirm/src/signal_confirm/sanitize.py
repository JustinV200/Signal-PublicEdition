"""Makes untrusted text safe to show in the dialog: no fake lines, no hidden or reordered text.

Unicode categories C* (controls, and format characters such as bidi overrides)
and Z* (separators such as U+2028) become spaces and runs of spaces collapse.
Long text keeps both ends around an ellipsis, because the harmful part of a
long input can sit at the end.
"""

import unicodedata

ELISION = " \u2026 "
# Unicode category prefixes replaced by a space. Z* includes U+0020 itself, which
# is harmless and simply maps to a space.
UNSAFE_CATEGORY_PREFIXES = ("C", "Z")
# Eliding gives one third of the kept characters to the tail and the rest to the head.
TAIL_SHARE_DIVISOR = 3


def sanitize_text(text: str, max_chars: int) -> str:
    """Flatten `text` to one safe line of at most `max_chars` characters.

    Args:
        text: Untrusted text, e.g. a stored name or a page-supplied label.
        max_chars: The longest result allowed.

    Returns:
        The text with every C*/Z* character turned into a space, runs of
        spaces collapsed, both ends trimmed, and the middle elided if too long.
    """
    spaced = "".join(
        " " if unicodedata.category(char)[0] in UNSAFE_CATEGORY_PREFIXES else char for char in text
    )
    # split() with no argument splits on runs of whitespace, so this collapses them.
    return elide(" ".join(spaced.split()), max_chars)


def sanitize_message(message: str, max_chars: int) -> str:
    """Sanitize a multi-line message, keeping the caller's own line breaks.

    Each "\\n"-separated line is sanitized like sanitize_text, so a CR, U+2028
    or bidi override inside a line can't start a fake line or reorder text.
    Runs of blank lines collapse to one, so padding can't push text out of view.

    Args:
        message: The dialog body; "\\n" separates lines.
        max_chars: The longest result allowed.

    Returns:
        The sanitized lines joined with "\\n", the middle elided if too long.
    """
    lines = [sanitize_text(line, max_chars) for line in message.split("\n")]
    kept = [line for index, line in enumerate(lines) if line or (index > 0 and lines[index - 1])]
    return elide("\n".join(kept).strip("\n"), max_chars)


def elide(text: str, max_chars: int) -> str:
    """Cut `text` to `max_chars` by replacing its middle with " \u2026 ".

    Args:
        text: Any text.
        max_chars: The longest result allowed.

    Returns:
        `text` unchanged if it fits; otherwise its head and tail around the
        ellipsis, exactly `max_chars` long. When `max_chars` leaves no room for
        both ends, a plain cut.
    """
    if len(text) <= max_chars:
        return text
    kept_chars = max_chars - len(ELISION)
    if kept_chars < TAIL_SHARE_DIVISOR:
        return text[: max(max_chars, 0)]
    tail_chars = kept_chars // TAIL_SHARE_DIVISOR
    head_chars = kept_chars - tail_chars
    return text[:head_chars] + ELISION + text[len(text) - tail_chars :]
