"""The 4-change budget: which validated items the writer gets this check, and how many wait.

The guard lets at most 5 existing lines change per file (kb MAX_REMOVED_LINES_PER_FILE),
and the first check of a term has more than that to do in this week's plan. So the
runner, not the model, keeps every check under it:
- A change is an item that should alter existing open todo lines: a done item to
  tick (every open line that mentions it), or an overdue one to move under
  "## Overdue" (one line). Changes go to the writer in priority order (overdue, then
  due soon, then the rest) while they touch at most MAX_CHANGES lines in all, so
  even if they all land in one file they stay under the guard's cap. The others wait
  for the next check, which works from the sites' state again ("N more next check").
- An add is an item no open todo line mentions yet (new work, or overdue work with no
  line): the writer adds a line, or puts it in inbox.md if it can't place it.
- An item an open line already shows as it is (or a done item with no line) needs
  nothing, so the writer never sees it, and it can't use up the budget every check.
At most MAX_WRITER_ITEMS go to the writer in all.
"""

import re
from dataclasses import dataclass

from mail_digest.assignment_check.findings import DONE, Item

MAX_CHANGES = 4
MAX_WRITER_ITEMS = 20
OPEN_TODO = re.compile(r"[ \t]*[-*+][ \t]+\[ \][ \t]")
HEADING = re.compile(r"#{1,6} ")
OVERDUE_HEADING = "## overdue"
# shortcut: KB lines often name an item by its code ("A18"), not the site's full name,
# so a leading code like A18 or HW3 also counts as a mention. A line naming the item
# some other way isn't found; the item is then an add, and the routine skips it if
# it reads an existing line for it. Upgrade if real checks keep missing lines.
ITEM_CODE = re.compile(r"[a-z]{0,4}[0-9]{1,3}")


@dataclass(frozen=True)
class OpenLine:
    """One open todo line of an editable file, casefolded, and whether it's under Overdue."""

    text: str
    is_overdue: bool


@dataclass(frozen=True)
class Selection:
    """What the writer gets: changes to existing lines, new lines, and how many changes wait."""

    changes: tuple[Item, ...] = ()
    adds: tuple[Item, ...] = ()
    spilled: int = 0


def open_lines(texts: dict[str, str]) -> list[OpenLine]:
    """Every open todo line of the editable files' texts (path -> text)."""
    lines = []
    for text in texts.values():
        is_overdue = False
        for line in text.split("\n"):
            if HEADING.match(line):
                is_overdue = line.strip().casefold() == OVERDUE_HEADING
            elif OPEN_TODO.match(line):
                lines.append(OpenLine(" ".join(line.split()).casefold(), is_overdue))
    return lines


def select_items(items: tuple[Item, ...], lines: list[OpenLine]) -> Selection:
    """The writer's items this check (see the module docstring)."""
    changes, adds, used, waiting = [], [], 0, 0
    for item in sorted(items, key=_priority):
        cost, is_add = _change_cost(item, [line for line in lines if _mentions(line.text, item)])
        if is_add:
            adds.append(item)
        elif cost and used + cost <= MAX_CHANGES:
            changes.append(item)
            used += cost
        elif cost:
            waiting += 1
    room = MAX_WRITER_ITEMS - len(changes)
    return Selection(tuple(changes), tuple(adds[:room]), spilled=waiting)


def _change_cost(item: Item, mentioned: list[OpenLine]) -> tuple[int, bool]:
    """(how many existing lines item changes, whether it's an add instead).

    A tick changes every open line that mentions the item (the plan can have it
    under Overdue and in its course's section). A move under Overdue changes one;
    an item a line already shows under Overdue needs none.
    """
    if item.status == DONE:
        return len(mentioned), False
    if not mentioned:
        return 0, True
    if item.overdue and not any(line.is_overdue for line in mentioned):
        return 1, False
    return 0, False


def _priority(item: Item) -> int:
    """Overdue first, then due soon, then everything else (sorted is stable)."""
    return 0 if item.overdue else 1 if item.due_soon else 2


def _mentions(line: str, item: Item) -> bool:
    """True if the folded todo line is about item: its course tag, and its name or code."""
    if f"[{item.course}]" not in line:
        return False
    name = " ".join(item.name.split()).casefold()
    if name in line:
        return True
    code = re.split(r"[\s:.,-]", name, maxsplit=1)[0]
    return (
        bool(ITEM_CODE.fullmatch(code)) and re.search(rf"\b{re.escape(code)}\b", line) is not None
    )
