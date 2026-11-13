"""The task grid as board items: outlines, one text per box, the status numbers, header and usage.

Colours follow the whiteboard-task-grid layout (cyan review, yellow building,
pink needs you, white queued, lime done), but the owner is colourblind, so every
box also carries its bold white status number top-right, the header gives the
number key, and a box that needs the owner says "YOU:". Task text goes in text
items, which the board page renders as plain text, never markup; the one SVG
item holds only the numbers.
"""

import json
from datetime import datetime
from typing import Any

from signal_tasks import STATUS_NUMBERS, STATUS_WORDS, Task, TaskGroups, UsageSummary

from whiteboard.tasks_grid.layout import (
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    HEADER_BOX,
    HEADER_TEXT,
    USAGE_TEXT,
    Box,
    plan_grid,
)

COLOURS = {
    "review": "#00e5ff",
    "building": "#ffff00",
    "needs_you": "#ff99ff",
    "queued": "#ffffff",
    "done": "#7cff00",
}
NEEDS_YOU_OUTLINE = "#ff66ff"
WHITE = "#ffffff"
TEXT_INSET = 12.0
# Room left of the text for the status number in the box's top-right corner. The text is
# box width - 55: 200 px in the 4-column layout (the memory layout's value), 285 px in the
# 3-column one. The number is centred 18 px in from the right edge at 30 px bold, so it
# starts about 28 px in; text ending 43 px in clears it by ~15 px in both layouts.
NUMBER_ROOM = 55.0
NUMBER_FONT_PX = 30
HEADER_FONT_PX = 18.0
USAGE_FONT_PX = 19.0
GROUP_NAMES_SHOWN = 3
NUMBER_KEY = "#: 1 review 2 building 3 NEEDS YOU 4 queued 5 done"
# Whose tasks these are, first in the header as in the memory layout.
SESSION_NAME = "Signal main session"
SECONDS_PER_MINUTE = 60

Item = dict[str, Any]


def grid_items(groups: TaskGroups, usage: UsageSummary, now: datetime) -> list[Item]:
    """Every item of the grid, in design pixels (1114x720; scale with scale_items).

    Args:
        groups: The tasks in display order (signal_tasks.group_tasks).
        usage: The usage line's data.
        now: For the usage line's age.
    """
    plan = plan_grid(len(groups.active))
    shown = groups.active[: len(plan.active)]
    boxes = [(box, task.status) for box, task in zip(plan.active, shown, strict=True)]
    boxes += [(plan.queued, "queued"), (plan.done, "done")]
    texts = [
        _text(f"t-{task.id}", box, _task_text(task), task.status)
        for box, task in zip(plan.active, shown, strict=True)
    ]
    texts.append(_text("queued", plan.queued, _queued_text(groups.queued), "queued"))
    texts.append(_text("done", plan.done, _done_text(groups.done), "done"))
    return [
        _outlines(boxes),
        *texts,
        _numbers(boxes),
        _plain("header", HEADER_TEXT, _header_text(groups, plan.hidden), HEADER_FONT_PX),
        _plain("usage", USAGE_TEXT, _usage_text(usage, now), USAGE_FONT_PX),
    ]


def scale_items(items: list[Item], width: float, height: float) -> list[Item]:
    """The items moved from design pixels onto a width x height board."""
    sx, sy = width / DESIGN_WIDTH, height / DESIGN_HEIGHT
    scaled = []
    for item in items:
        box = {"x": item["x"] * sx, "y": item["y"] * sy, "w": item["w"] * sx, "h": item["h"] * sy}
        scaled.append({**item, **box})
    return scaled


def _task_text(task: Task) -> str:
    lines = [f"{task.name}  {task.pct}%", STATUS_WORDS[task.status]]
    if task.you:
        lines.append(f"YOU: {task.you}")
    if task.next:
        lines.append(f"Next: {task.next}")
    return "\n".join(lines)


def _queued_text(tasks: tuple[Task, ...]) -> str:
    # The console page's wording: "Queued: 6 tasks, none started".
    noun = "task" if len(tasks) == 1 else "tasks"
    started = sum(1 for task in tasks if task.pct > 0)
    progress = f"{started} started" if started else "none started"
    return _group_lines(f"Queued: {len(tasks)} {noun}, {progress}", tasks)


def _done_text(tasks: tuple[Task, ...]) -> str:
    return _group_lines(f"Done today: {len(tasks)}", tasks)


def _group_lines(heading: str, tasks: tuple[Task, ...]) -> str:
    lines = [heading]
    lines += [f"{task.name} {task.pct}%" for task in tasks[:GROUP_NAMES_SHOWN]]
    if len(tasks) > GROUP_NAMES_SHOWN:
        lines.append(f"+ {len(tasks) - GROUP_NAMES_SHOWN} more")
    return "\n".join(lines)


def _header_text(groups: TaskGroups, hidden: int) -> str:
    overall = f", {groups.overall_pct}% overall" if groups.overall_pct is not None else ""
    needs = f", {groups.needs_you} NEED YOU" if groups.needs_you else ""
    more = f" ({hidden} not shown)" if hidden else ""
    return f"{SESSION_NAME}: {len(groups.active)} active{overall}{needs}{more}   {NUMBER_KEY}"


def _usage_text(usage: UsageSummary, now: datetime) -> str:
    five = f"{usage.five_hour.used_pct:.0f}%" if usage.five_hour else "--"
    week = f"{usage.seven_day.used_pct:.0f}%" if usage.seven_day else "--"
    if usage.updated_at is None:
        age = "no data"
    else:
        minutes = max(0, int((now - usage.updated_at).total_seconds() // SECONDS_PER_MINUTE))
        age = f"{minutes} min ago"
    return f"5h: {five}   Week: {week}\nAgents: {usage.agents}, {age}"


def _outlines(boxes: list[tuple[Box, str]]) -> Item:
    shapes = [_rect(Box(*HEADER_BOX), WHITE)]
    for box, status in boxes:
        colour = NEEDS_YOU_OUTLINE if status == "needs_you" else COLOURS[status]
        shapes.append(_rect(box, colour))
    content = json.dumps(shapes, separators=(",", ":"))
    style = {"color": WHITE, "stroke_width": 3.0, "rough": True}
    return {"id": "agents", "kind": "rough", "content": content, **_whole(), "style": style}


def _numbers(boxes: list[tuple[Box, str]]) -> Item:
    texts = "".join(
        f'<text x="{box.x + box.w - 18:g}" y="{box.y + 32:g}">{STATUS_NUMBERS[status]}</text>'
        for box, status in boxes
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {DESIGN_WIDTH:g} '
        f'{DESIGN_HEIGHT:g}"><g fill="{WHITE}" font-family="Segoe UI, sans-serif" '
        f'font-size="{NUMBER_FONT_PX}" font-weight="bold" text-anchor="middle">{texts}</g></svg>'
    )
    return {"id": "nums", "kind": "svg", "content": svg, **_whole()}


def _text(item_id: str, box: Box, content: str, status: str) -> Item:
    frame = {
        "x": box.x + TEXT_INSET,
        "y": box.y + TEXT_INSET,
        "w": box.w - NUMBER_ROOM,
        "h": box.h - 2 * TEXT_INSET,
    }
    style = {"color": COLOURS[status]}
    return {"id": item_id, "kind": "text", "content": content, **frame, "style": style}


def _plain(item_id: str, frame: tuple[float, ...], content: str, font_px: float) -> Item:
    x, y, w, h = frame
    style = {"color": WHITE, "font_size": font_px}
    box = {"x": x, "y": y, "w": w, "h": h}
    return {"id": item_id, "kind": "text", "content": content, **box, "style": style}


def _rect(box: Box, colour: str) -> dict[str, Any]:
    return {"shape": "rect", "x": box.x, "y": box.y, "w": box.w, "h": box.h, "color": colour}


def _whole() -> dict[str, float]:
    return {"x": 0.0, "y": 0.0, "w": DESIGN_WIDTH, "h": DESIGN_HEIGHT}
