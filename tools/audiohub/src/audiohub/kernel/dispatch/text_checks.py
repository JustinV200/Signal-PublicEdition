"""Text heuristics behind the dispatcher safeguards: repeated messages and code-heavy text.

`is_near_duplicate` decides whether a drop really repeats something already
delivered. `is_code_heavy` decides whether a short message is still too
awkward to read aloud verbatim (code, logs, paths, lists), so condensing it
is allowed.
"""

import re

# TODO: move these tunables into KernelSettings once audiohub.config is free to edit.
CODE_FENCE = "```"
CODE_SYMBOLS = frozenset("{}[]()<>;=|\\/$#_`")
CODE_SYMBOL_SHARE = 0.08  # share of non-space characters; plain English sits near 0.01
CODE_LINE_SHARE = 0.5  # share of non-blank lines that look like code, logs or list items
MIN_LINES_FOR_LINE_SHAPE = 3

# A line that looks like a list item, indented code, a path, or code punctuation.
_CODE_LIKE_LINE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s|^\s{4,}\S|[{};]|[\\/]\w+[\\/]|=>|==")

# Only trailing sentence enders are ignored; every other character counts.
_TRAILING_ENDERS = " .!"


def is_near_duplicate(text: str, other: str) -> bool:
    """True if `text` is `other` again, apart from whitespace and a trailing "." or "!".

    Deliberately strict: no case folding, Unicode or punctuation normalization,
    because each of those merged pairs that contradict ("5 mW" vs "5 MW",
    "10⁶" vs "106", "(500)" vs "500"). Too strict only repeats a message now
    and then; too loose loses information.

    Args:
        text: The message that would be dropped.
        other: The delivered text it might repeat.

    Returns:
        Whether both texts have the same canonical form.
    """
    return _canon(text) == _canon(other)


def is_code_heavy(text: str) -> bool:
    """True if `text` is mostly code, log lines, paths or list items.

    Args:
        text: A message text.

    Returns:
        Whether it contains a code fence, has a high share of code symbols, or
        most of its lines (when it has several) look like code or list items.
    """
    if CODE_FENCE in text:
        return True
    visible = [char for char in text if not char.isspace()]
    if (
        visible
        and sum(char in CODE_SYMBOLS for char in visible) / len(visible) >= CODE_SYMBOL_SHARE
    ):
        return True
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < MIN_LINES_FOR_LINE_SHAPE:
        return False
    code_like = sum(bool(_CODE_LIKE_LINE.search(line)) for line in lines)
    return code_like / len(lines) >= CODE_LINE_SHARE


def _canon(text: str) -> str:
    """Collapse runs of whitespace and drop trailing spaces, periods and exclamation marks."""
    return " ".join(text.split()).rstrip(_TRAILING_ENDERS)
