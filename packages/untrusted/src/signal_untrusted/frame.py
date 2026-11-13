"""The frame outside text goes in whenever a model reads it: data, never instructions.

Generalised from the whiteboard's plan_data helper (whiteboard/todo/plan_frame.py),
which should switch to this once its TODO-view round lands. One fixed trusted line
says what the data is, then the data goes in as JSON inside one tag pair.
"""

import json
import re
from typing import Any

# Tag names like the other tools' frames: untrusted_email_content, untrusted_page_content.
TAG_PATTERN = re.compile(r"^untrusted_[a-z_]{1,48}_content$")


def safe_json(data: Any) -> str:
    """`data` as one line of JSON with no `<` and no non-ASCII or control character.

    Every `<` is written as the escape \\u003c (still the same JSON), so the text
    can't close a frame early or open a look-alike tag. json.dumps also escapes every
    non-ASCII and control character, so line separators can't hide text.

    Raises:
        TypeError: The data isn't JSON-serialisable.
    """
    return json.dumps(data).replace("<", "\\u003c")


def frame(data: Any, tag: str) -> str:
    """`data` as safe_json inside `<tag>...</tag>`.

    Args:
        data: Anything json.dumps takes.
        tag: The tag name, matching TAG_PATTERN.

    Returns:
        The framed JSON, on one line.

    Raises:
        ValueError: The tag doesn't match TAG_PATTERN.
        TypeError: The data isn't JSON-serialisable.
    """
    if not TAG_PATTERN.fullmatch(tag):
        raise ValueError(f"bad frame tag {tag!r}")
    return f"<{tag}>{safe_json(data)}</{tag}>"


def framed(trusted_line: str, data: Any, tag: str) -> str:
    """The trusted line, then `data` in the frame on the next line.

    Args:
        trusted_line: Fixed text the caller wrote (never outside text), on one line.
        data: Anything json.dumps takes.
        tag: The tag name, matching TAG_PATTERN.

    Returns:
        The two lines.

    Raises:
        ValueError: The tag is bad, or the trusted line has a line break.
        TypeError: The data isn't JSON-serialisable.
    """
    if "\n" in trusted_line or "\r" in trusted_line:
        raise ValueError("the trusted line must be one line")
    return f"{trusted_line}\n{frame(data, tag)}"
