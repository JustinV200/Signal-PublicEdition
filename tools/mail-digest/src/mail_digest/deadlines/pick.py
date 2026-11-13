"""Routine step 5 in code: which plan todos to announce now, with stable keys.

The runner reads this week's plan (last week's if the week hasn't rolled over yet)
and next week's (for a todo due early Monday), and picks every open todo due within
DUE_SOON_HOURS (kind `due`) and every open todo under `## Overdue` (kind `overdue`).
The key is the kind plus a slug of the todo's tag and name, which leaves out its due
marker and notes, so a new note or a new time on the same day doesn't make it a new
item: the announcer speaks each key once. A due key also has the due day
(`due|2026-10-26|hist-205-lab`), so a weekly todo with the same name is spoken each
week, and a todo moved to another day is spoken again for its new day.

Keys made before the due day was added (`due|<slug>`) don't match the new ones, so
an item due within 24 hours on the first run after the change is spoken once more.
That's at most that day's due items, once, so they're left to expire from the state.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from mail_digest.announce import Announcement
from mail_digest.claude import clean_sentence, slugify
from mail_digest.deadlines.todos import PlanTodo, open_todos
from mail_digest.kb import find_plan
from mail_digest.settings import DUE_SOON_HOURS

log = logging.getLogger(__name__)

DUE_SOON = timedelta(hours=DUE_SOON_HOURS)
DAYS_PER_WEEK = 7


def pick_announcements(life_dir: Path, now: datetime) -> list[Announcement]:
    """The due and overdue items of this week's and next week's plans, each key once.

    Each run rolls the week over first (steps.roll_week), but if that failed or the
    week falls between terms, last week's plan stands in until this week's exists.
    now is timezone-aware local time. A plan that can't be read is logged and
    skipped, so the run's own alerts are still spoken.
    """
    picks: dict[str, Announcement] = {}
    week = timedelta(days=DAYS_PER_WEEK)
    today = now.date()
    plans = (
        find_plan(life_dir, today) or find_plan(life_dir, today - week),
        find_plan(life_dir, today + week),
    )
    for plan in plans:
        if plan is None:
            continue
        try:
            text = (life_dir / plan).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            log.warning("couldn't read %s for due items: %s", plan, error)
            continue
        for pick in select_announcements(text, now):
            picks.setdefault(pick.key, pick)
    return list(picks.values())


def select_announcements(plan_text: str, now: datetime) -> list[Announcement]:
    """The items of one plan to announce at now (see the module docstring)."""
    local_now = now.replace(tzinfo=None)  # due markers are local wall-clock times
    picks = []
    for todo in open_todos(plan_text):
        if todo.is_overdue:
            picks.append(_announcement("overdue", todo, "overdue"))
        elif todo.due and local_now < todo.due <= local_now + DUE_SOON:
            picks.append(_announcement("due", todo, f"due {_when(todo, local_now)}"))
    return [pick for pick in picks if pick]


def _announcement(kind: str, todo: PlanTodo, status: str) -> Announcement | None:
    """The item, or None if nothing keyable or speakable is left of it.

    The sentence puts the course and status before the name ("CHEM 120, due today at
    10:00: Lab 3"), so the cut to MAX_SENTENCE_CHARS only ever shortens the name.
    """
    slug = slugify(f"{todo.tag} {todo.name}")
    lead = f"{todo.tag.replace('-', ' ').upper()}, {status}" if todo.tag else status.capitalize()
    sentence = clean_sentence(f"{lead}: {todo.name}")
    key = f"due|{todo.due:%Y-%m-%d}|{slug}" if kind == "due" and todo.due else f"{kind}|{slug}"
    return Announcement(key, sentence) if slug and sentence else None


def _when(todo: PlanTodo, local_now: datetime) -> str:
    """When it's due, said aloud: "today at 17:00", "tomorrow by end of day" and so on."""
    day = "today" if todo.due.date() == local_now.date() else "tomorrow"
    return f"{day} at {todo.due:%H:%M}" if todo.has_time else f"{day} by end of day"
