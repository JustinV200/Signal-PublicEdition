"""clean_text: make outside text (a feed headline, a calendar title) safe and short to show.

Tags are stripped, entities unescaped, control and format characters (zero-width,
bidi overrides) dropped, whitespace collapsed, and the result cut to a length. The page
still sets it with textContent; this keeps it one tidy line and caps what a feed or a
calendar invite can put on the board.
"""

import html
import re
import unicodedata

_TAG = re.compile(r"<[^>]*>")
ELLIPSIS = "…"


def clean_text(raw: str, max_chars: int) -> str:
    """One display line from untrusted text.

    Args:
        raw: The text as received.
        max_chars: The longest result; longer text is cut and ends in an ellipsis.

    Returns:
        The cleaned text ("" if nothing printable is left).
    """
    text = html.unescape(_TAG.sub(" ", raw))
    # Unicode category C: controls, format characters, private use, unassigned. Line
    # breaks and tabs are controls too, but they separate words: they become spaces.
    text = "".join(
        " " if char.isspace() else char
        for char in text
        if char.isspace() or not unicodedata.category(char).startswith("C")
    )
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = text[: max_chars - 1].rstrip() + ELLIPSIS
    return text
