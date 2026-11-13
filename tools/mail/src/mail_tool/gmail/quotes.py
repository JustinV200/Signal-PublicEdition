"""strip_quoted: drop the earlier mail a reply quotes, for the thread view.

In a thread the quoted messages are already there in full, so repeating them
in every reply only costs tokens. Plain-text replies quote with an
"On <date>, <name> wrote:" line and/or lines starting with '>'.
"""

import re

# Gmail's and most clients' attribution line above the quoted message.
_ATTRIBUTION_LINE = re.compile(r"^On .+ wrote:\s*$")
QUOTE_PREFIX = ">"


def strip_quoted(text: str) -> str:
    """The text without its quoted mail: every '>' line and "On ... wrote:" line removed.

    After an attribution line the rest is cut, unless it is an inline or
    bottom-posted reply (a '>' line first, the writer's own text later), where
    the writer's lines are kept. Removing (not cutting at) '>' lines keeps the
    answers that sit between quoted lines.
    """
    lines = text.splitlines()
    kept = []
    i = 0
    while i < len(lines):
        span = _attribution_span(lines, i)
        if span:
            if not _is_interleaved(lines[i + span :]):
                break  # top-posted: everything below is the quoted mail
            i += span
            continue
        if not _is_quoted(lines[i]):
            kept.append(lines[i])
        i += 1
    return "\n".join(kept).rstrip()


def _is_quoted(line: str) -> bool:
    return line.lstrip().startswith(QUOTE_PREFIX)


def _attribution_span(lines: list[str], i: int) -> int:
    """How many lines the attribution at lines[i] takes: 0 (none), 1, or 2.

    Gmail wraps a long one inside the address: "On ..., Alice <" / "a@x.com> wrote:".
    """
    line = lines[i].strip()
    if _ATTRIBUTION_LINE.match(line):
        return 1
    joined = f"{line} {lines[i + 1].strip()}" if i + 1 < len(lines) else ""
    return 2 if line.startswith("On ") and _ATTRIBUTION_LINE.match(joined) else 0


def _is_interleaved(rest: list[str]) -> bool:
    """True if `rest` starts with a '>' line and has the writer's own text after it.

    An HTML reply's quote has no '>' prefixes, so its first line is unquoted
    and the whole rest is treated as quoted mail.
    """
    text_lines = [line for line in rest if line.strip()]
    return bool(text_lines) and _is_quoted(text_lines[0]) and not all(map(_is_quoted, text_lines))
