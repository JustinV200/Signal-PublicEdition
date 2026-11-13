"""Join markdown lines into spoken sentences, dropping block-level markers.

Second half of `cleaning.clean_for_speech`. It works on lines whose inline
markup is already gone, and follows markdown's paragraph rules:
- Consecutive prose lines are one paragraph, joined with a space.
- A blank line or horizontal rule ends a paragraph.
- A heading is a sentence of its own.
- A bullet or numbered item starts a new paragraph that continuation lines
  can join.
Each paragraph is given closing punctuation, so the voice pauses between them.
"""

import re
from enum import Enum

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)(?:\s+#+)?\s*$")
# Three or more of the same rule character, optionally spaced ("- - -").
# "===" also covers setext heading underlines.
_RULE = re.compile(r"^\s{0,3}([-*_=])(?:\s*\1){2,}\s*$")
_BLOCKQUOTE = re.compile(r"^\s*(?:>\s?)+")
# Up to three digits, so a line opening with a year ("2024. It ...") is
# left alone. The required whitespace keeps "3.5 is out" intact.
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
_WHITESPACE = re.compile(r"\s+")
# Punctuation that already gives the voice a pause at the end of a block.
_PAUSE_PUNCTUATION = ".!?:;"
# Closing quotes and brackets sit after the real final punctuation.
_CLOSERS = "\"')]}”’»"


class _LineKind(Enum):
    """How a line relates to the paragraph before it."""

    BREAK = "break"  # blank line or rule: ends the current paragraph
    HEADING = "heading"  # a closed paragraph of its own
    ITEM = "item"  # starts a new paragraph
    TEXT = "text"  # continues the current paragraph


def join_blocks(lines: list[str]) -> str:
    """Join lines into one string of sentences, one per paragraph or item.

    Args:
        lines: Lines of text with inline markdown already removed.

    Returns:
        The paragraphs joined by single spaces, each ending in punctuation.
    """
    paragraphs: list[list[str]] = [[]]
    for line in lines:
        kind, content = _classify(line)
        if kind is not _LineKind.TEXT:
            paragraphs.append([])
        if content:
            paragraphs[-1].append(content)
        if kind is _LineKind.HEADING:
            paragraphs.append([])
    sentences = (_end_with_pause(" ".join(parts)) for parts in paragraphs if parts)
    return _WHITESPACE.sub(" ", " ".join(sentences)).strip()


def _classify(line: str) -> tuple[_LineKind, str]:
    """Return the line's kind and its content with block markers removed."""
    line = _BLOCKQUOTE.sub("", line)
    if not line.strip() or _RULE.match(line):
        return _LineKind.BREAK, ""
    heading = _HEADING.match(line)
    if heading:
        return _LineKind.HEADING, heading.group(1).strip()
    item = _LIST_ITEM.match(line)
    if item:
        return _LineKind.ITEM, line[item.end() :].strip()
    return _LineKind.TEXT, line.strip()


def _end_with_pause(sentence: str) -> str:
    """Add a full stop unless the sentence already ends in pause punctuation."""
    sentence = sentence.strip()
    core = sentence.rstrip(_CLOSERS)
    if not core or core[-1] in _PAUSE_PUNCTUATION:
        return sentence
    return sentence + "."
