"""Pure text helpers over a redacted snapshot: pages, a ref's subtree, and text search.

The snapshot tool serves a long snapshot in pages cut at line boundaries, or
just the lines under one ref; find searches it. They only ever see the text the
snapshot tool already redacted (snapshot_cache), never the live page, so they
can't show anything a full snapshot wouldn't.
"""

from bisect import bisect_right
from dataclasses import dataclass

from browser_tool.redaction import indent_of, label_of, parse_line

# How many ancestors a find result names, nearest last.
MAX_PATH_DEPTH = 4
# Long names and lines are cut in find results, to keep them short.
MAX_PATH_NAME_CHARS = 40
MAX_MATCH_LINE_CHARS = 300
ELLIPSIS = "..."


@dataclass(frozen=True)
class Match:
    """One find result.

    Attributes:
        line_no: 1-based line number in the whole snapshot.
        page: 1-based snapshot page the line is on.
        ref: The line's own ref, else its nearest ancestor's, else None.
        path: Ancestor labels, outermost shown first, e.g. ('main', 'form "Compose"').
        text: The line, stripped and cut to MAX_MATCH_LINE_CHARS.
    """

    line_no: int
    page: int
    ref: str | None
    path: tuple[str, ...]
    text: str


def page_bounds(text: str, max_chars: int) -> list[tuple[int, int]]:
    """Split `text` into pages of at most `max_chars`, cut after a newline where possible.

    A single line longer than max_chars is cut mid-line. Empty text is one empty page.

    Returns:
        (start, end) offsets of each page, covering the whole text in order.
    """
    bounds = []
    start = 0
    while len(text) - start > max_chars:
        cut = text.rfind("\n", start, start + max_chars)
        end = cut + 1 if cut >= start else start + max_chars
        bounds.append((start, end))
        start = end
    bounds.append((start, len(text)))
    return bounds


def page_text(text: str, bounds: tuple[int, int]) -> str:
    """The text of one page from page_bounds, without its trailing newline."""
    start, end = bounds
    return text[start:end].rstrip("\n")


def subtree(text: str, ref: str) -> str | None:
    """The line carrying `ref` and every more-indented line under it, or None if no line has it."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        parsed = parse_line(line)
        if parsed is None or parsed.ref != ref:
            continue
        end = index + 1
        while end < len(lines) and indent_of(lines[end]) > parsed.indent:
            end += 1
        return "\n".join(lines[index:end])
    return None


def find_matches(
    text: str, query: str, max_chars: int, max_results: int
) -> tuple[list[Match], int]:
    """Lines of `text` containing `query` (case-insensitive), with their refs and ancestors.

    Args:
        text: The redacted snapshot.
        query: The text to look for.
        max_chars: The snapshot page size, to say which page each line is on.
        max_results: How many matches to return.

    Returns:
        The first max_results matches, and how many lines matched in all.
    """
    needle = query.casefold()
    # Split at newlines only, not splitlines(): the offsets must match page_bounds.
    lines = text.split("\n")
    page_starts = [start for start, _end in page_bounds(text, max_chars)]
    matches = []
    total = 0
    offset = 0
    for index, line in enumerate(lines):
        if needle in line.casefold():
            total += 1
            if len(matches) < max_results:
                page = bisect_right(page_starts, offset)
                matches.append(_match_at(lines, index, page))
        offset += len(line) + 1  # split dropped the newline
    return matches, total


def _match_at(lines: list[str], index: int, page: int) -> Match:
    """Build the Match for lines[index]: its ref and the labels of its ancestors."""
    own = parse_line(lines[index])
    ref = own.ref if own is not None else None
    path: list[str] = []
    indent = indent_of(lines[index])
    for earlier in reversed(lines[:index]):
        if indent == 0:
            break
        parent = parse_line(earlier)
        if parent is None or parent.indent >= indent:
            continue
        indent = parent.indent
        ref = ref or parent.ref
        if len(path) < MAX_PATH_DEPTH:
            path.insert(0, _cut(label_of(parent), MAX_PATH_NAME_CHARS))
    shown = _cut(lines[index].strip(), MAX_MATCH_LINE_CHARS)
    return Match(line_no=index + 1, page=page, ref=ref, path=tuple(path), text=shown)


def _cut(text: str, max_chars: int) -> str:
    """`text`, cut to max_chars with an ellipsis when longer."""
    return text if len(text) <= max_chars else text[: max_chars - len(ELLIPSIS)] + ELLIPSIS
