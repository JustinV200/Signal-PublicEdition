"""Course chips for the idle view: a tag's short display name and its colour.

The colour is the TODO view's (todo.view.tag_color), so a course looks the same on
both. The name comes from [idle] tag_labels ("tag=Label"), else the tag title-cased
with its dashes as spaces. Calendar events get one neutral chip instead.
"""

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from whiteboard.todo.view import tag_color

log = logging.getLogger(__name__)

# Calendar events have no course: a neutral grey chip that says where they came from.
CALENDAR_CHIP = {"label": "Cal", "color": "#cfd8dc"}

Chip = dict[str, Any]


def parse_tag_labels(entries: Iterable[str]) -> dict[str, str]:
    """Read [idle] tag_labels ("tag=Label" strings) into {tag: label}; tags are lowercased.

    A malformed entry is logged and skipped, so one typo can't stop the daemon.
    """
    labels = {}
    for entry in entries:
        tag, separator, label = entry.partition("=")
        if not separator or not tag.strip() or not label.strip():
            log.warning("[idle] tag_labels: ignoring %r (expected tag=Label)", entry)
            continue
        labels[tag.strip().lower()] = label.strip()
    return labels


def chip(tag: str, labels: Mapping[str, str]) -> Chip | None:
    """The chip for a plan tag, or None for an untagged line.

    Args:
        tag: The plan's tag, e.g. "chem-120".
        labels: From parse_tag_labels.
    """
    if not tag:
        return None
    label = labels.get(tag.lower())
    if label is None:
        label = " ".join(word[:1].upper() + word[1:] for word in tag.split("-") if word)
    return {"label": label, "color": tag_color(tag)}
