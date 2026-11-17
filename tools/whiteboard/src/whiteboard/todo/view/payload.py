"""build_payload: the JSON the board page draws the TODO view from (static/todo.js).

Everything is plain data: positions from layout.py, labels, colours and flags. The
page puts every string in with textContent, so plan text is never parsed as HTML.
Tag colours come from a fixed palette of bright, projector-friendly colours, picked
by a hash of the tag so a course keeps its colour every day.
"""

import hashlib
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from whiteboard.todo.view.labels import DONE_LABEL, GROUP_OF_NOTE, GROUP_OVERDUE
from whiteboard.todo.view.layout import (
    KEYNOTE_FONT_PX,
    Box,
    HeadingPlace,
    RowPlace,
    TodoLayout,
)

# Bright on black, none of them red (red marks Overdue). With sha256 % 8 the five
# example tags (art-110, hist-205, chem-120, club, side-project)
# all get different colours.
TAG_COLORS = (
    "#00e5ff",  # cyan
    "#ffea00",  # yellow
    "#76ff03",  # lime
    "#ff4dff",  # magenta
    "#ffab40",  # orange
    "#82b1ff",  # periwinkle
    "#ff80ab",  # pink
    "#64ffda",  # aquamarine
)
UNTAGGED_COLOR = "#ffffff"
HEADING_COLORS = {GROUP_OVERDUE: "#ff5252", GROUP_OF_NOTE: "#ffd740"}
DAY_HEADING_COLOR = "#00e5ff"
TITLE = "TODO"
KEYNOTES_LABEL = "Keynotes"


@dataclass(frozen=True)
class HeaderText:
    """The view's header: today's date, when it was last synced, and an optional note."""

    date_label: str
    updated_label: str
    note: str = ""


def tag_color(tag: str) -> str:
    """The palette colour for a tag (case doesn't matter); white for no tag."""
    if not tag:
        return UNTAGGED_COLOR
    digest = hashlib.sha256(tag.lower().encode("utf-8")).digest()
    return TAG_COLORS[int.from_bytes(digest, "big") % len(TAG_COLORS)]


def build_payload(
    layout: TodoLayout,
    header: HeaderText,
    done_ids: Collection[str],
    hint_ids: Collection[str] = (),
) -> dict[str, Any]:
    """The page's TODO view data.

    Args:
        layout: Where everything goes.
        header: Header labels and the note shown when nothing is due.
        done_ids: Items to draw struck through and dimmed.
        hint_ids: Items to mark with a "done?" hint (an unsure board cross-out).
    """
    metrics = layout.metrics
    return {
        "title": TITLE,
        "date_label": header.date_label,
        "updated_label": header.updated_label,
        "note": header.note,
        "header": _box(layout.header),
        "body": _box(layout.body),
        "metrics": {
            "font_px": metrics.font_px,
            "tag_font_px": metrics.tag_font_px,
            "due_font_px": metrics.due_font_px,
            "check_w": metrics.check_w,
            "tag_w": metrics.tag_w,
        },
        "headings": [_heading(heading) for heading in layout.headings],
        "rows": [_row(place, done_ids, hint_ids) for place in layout.rows],
        "more": _more(layout),
        "keynotes": _keynotes(layout),
    }


def _row(place: RowPlace, done_ids: Collection[str], hint_ids: Collection[str]) -> dict[str, Any]:
    """One row's data; text_x is given relative to the row's own left edge."""
    entry = place.row.entry
    is_done = entry.id in done_ids
    return {
        "id": entry.id,
        "tag": entry.tag,
        "text": place.row.title,
        # A done row says so in words too, not only by its dimming, for colourblind users.
        "due_label": DONE_LABEL if is_done else place.row.due_label,
        "color": tag_color(entry.tag),
        "done": is_done,
        "hint": entry.id in hint_ids,
        "overdue": place.group_key == GROUP_OVERDUE,
        "text_x": place.text_x - place.box.x,
        "text_w": place.text_w,
        **_box(place.box),
    }


def _more(layout: TodoLayout) -> dict[str, Any] | None:
    """The "+N more" line, if rows were cut off."""
    if layout.more is None:
        return None
    return {"label": f"+{layout.hidden_rows} more", **_box(layout.more)}


def _keynotes(layout: TodoLayout) -> dict[str, Any] | None:
    """The keynotes block: its heading, lines and font size, or None without keynotes."""
    if layout.keynotes is None:
        return None
    return {
        "label": KEYNOTES_LABEL,
        "lines": list(layout.keynote_lines),
        "font_px": KEYNOTE_FONT_PX,
        **_box(layout.keynotes),
    }


def _heading(heading: HeadingPlace) -> dict[str, Any]:
    """A group heading's data: overdue red, of note amber, day headings cyan."""
    color = HEADING_COLORS.get(heading.group_key, DAY_HEADING_COLOR)
    return {"label": heading.label, "color": color, **_box(heading.box)}


def _box(box: Box) -> dict[str, float]:
    """A Box as JSON, rounded to tenths of a pixel."""
    return {"x": round(box.x, 1), "y": round(box.y, 1), "w": round(box.w, 1), "h": round(box.h, 1)}
