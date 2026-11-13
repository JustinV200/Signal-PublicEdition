r"""Markdown table shape for the line rules: which lines are table rows, and their cell counts.

GFM and VS Code's markdown-it render a table row with only as many cells as its
table's header has, and drop the rest without a trace. So line_rules.py rejects an
added row with more cells than that, or its extra cell's text would be hidden.

The count is exact because the line rules ban "\" and "`", the only ways to put a
literal "|" inside a cell. Rows are trimmed of ASCII spaces and tabs only, as GFM
trims them: GFM takes a leading no-break space for a cell of its own (markdown-it
doesn't), so this count is the larger of the two.

An added line can't be a delimiter row: it has no room for the " (mail)" tag, so
the line rules reject it. But an added header row can turn an existing line into
one, even with no "|" in it. In GFM, one with a ":" (":---", "-:") makes a 1-cell
table under any header line, even one with no "|". markdown-it needs a "|" in the
header, and then takes "---" too. So every such line counts as a delimiter row, a
thematic break or setext underline included; that only makes the check stricter.
The header row itself either has the delimiter row's cell count (every header cell
shows) or makes no table at all.

A delimiter row inside an open table (two tables with no blank line between) is
just another row to the renderers, which keep the first table's width. So it can
only narrow the width here, never widen it; a wider second table's rows are then
rejected, the safe direction.
"""

import re

# Markdown's own spacing. No-break spaces aren't: a line of them isn't blank.
MARKDOWN_SPACING = " \t"
CELL_SEPARATOR = "|"
# What GFM's scanner takes for spacing around a delimiter row. Only that test uses
# it: a line of "\v" isn't blank to GFM, so the table goes on past it. "\r" is a line
# ending to GFM, not spacing; line_rules.py refuses a file with a lone one.
DELIMITER_SPACING = " \t\v\f"
# A delimiter row once trimmed ("|---|:--:|", "--- | ---", ":---", "---"). One with
# no "|" counts too (see the module docstring).
DELIMITER_ROW = re.compile(r"\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?")


def table_widths(lines: list[str]) -> list[int | None]:
    """For each line, the header cell count of the table it's a row of, else None.

    A table runs from its delimiter row to the next blank line. A line there that
    starts another block (a list item, a heading) counts as a row too. That's
    stricter than the renderers, but it never misses a row. One pass, so a long
    file with many added lines stays cheap.
    """
    widths, width = [], None
    for line in lines:
        delimiter = line.strip(DELIMITER_SPACING)
        if not line.strip(MARKDOWN_SPACING):
            width = None
        elif DELIMITER_ROW.fullmatch(delimiter):
            # A new table: GFM makes none unless the header has this many cells too.
            # In an open table it's just a row, and the first table's width holds.
            count = cell_count(delimiter)
            width = count if width is None else min(width, count)
        widths.append(width)
    return widths


def cell_count(row: str) -> int:
    """How many cells a table row has: its "|"-separated parts, without the empty
    ones before a leading "|" and after a trailing one."""
    trimmed = row.strip(MARKDOWN_SPACING)
    inner = trimmed.removeprefix(CELL_SEPARATOR).removesuffix(CELL_SEPARATOR)
    return len(inner.split(CELL_SEPARATOR))
