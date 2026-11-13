"""The no-untick rule for site runs: a file's todo and ticked-todo counts mustn't drop.

Checker v2 runs with forbid_untick (line_rules.LineRules), so an edit to one file
fails if it leaves fewer todo lines ("- [ ]" and "- [x]") or fewer ticked ones than
before. Counting, rather than pairing removed and added lines, lets a tick (an open
line replaced by a ticked one) and a move under "## Overdue" through. It's net-only:
one untick plus one tick in the same file passes, and so does a delete plus an add.
It stops the bulk case (wiping or unticking a section); the line caps bound a swap.
"""

import re

# A todo as life/README.md writes them (`- [ ] [tag] task`), any list marker or indent.
TODO_LINE = re.compile(r"[ \t]*[-*+][ \t]+\[[ xX]\][ \t]")
TICKED_LINE = re.compile(r"[ \t]*[-*+][ \t]+\[[xX]\][ \t]")


def untick_problems(before: str, after: str) -> list[str]:
    """Why the edit from before to after drops todos or ticks ([] if it doesn't)."""
    problems = []
    for label, pattern in (("todo", TODO_LINE), ("ticked todo", TICKED_LINE)):
        old, new = _count(pattern, before), _count(pattern, after)
        if new < old:
            problems.append(f"{label} lines dropped from {old} to {new}")
    return problems


def _count(pattern: re.Pattern[str], text: str) -> int:
    """How many lines of text start with pattern (lines split on "\n", as line_rules does)."""
    return sum(1 for line in text.split("\n") if pattern.match(line))
