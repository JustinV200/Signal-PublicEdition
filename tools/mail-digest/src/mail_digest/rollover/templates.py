"""Loads the week templates and fills in their `<date>` placeholders.

A template is life/templates/week-<name>.md if the owner made one, else the built-in
default below (so a new life/ needs no templates). Copy a default there and edit it
(a section per course or area, say) to change what each new week starts with.

Every placeholder follows a weekday name (`Mon <date> to Sun <date>`, `## Tue <date>`),
so each gets that weekday's date in the new week. A placeholder left over would make
the KB guard refuse every later edit to the file (it reads `<date>` as HTML), so one
that can't be filled is an error.
"""

import re
from pathlib import Path

from mail_digest.rollover.weeks import Week

TEMPLATES_DIR = "templates"
PLACEHOLDER = "<date>"
WEEKDAY_PLACEHOLDER = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun) <date>")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEEK_TITLE = "(Mon <date> to Sun <date>)"
DEFAULT_TEMPLATES = {
    "plan": f"# Week plan {WEEK_TITLE}\n\n## Overdue\n\n## Priorities\n",
    "log": f"# Week log {WEEK_TITLE}\n\n"
    + "\n\n".join(f"## {day} {PLACEHOLDER}" for day in WEEKDAYS)
    + "\n",
    "review": f"# Week review {WEEK_TITLE}\n\n"
    "## Done\n\n## Slipped\n\n## Carried over\n\n## Notes\n",
}


class TemplateError(ValueError):
    """A week template has a placeholder that can't be filled, or no such template exists."""


def fill_template(life_dir: Path, name: str, week: Week) -> str:
    """The week-<name> template with its dates filled in for `week`, as LF text.

    Raises TemplateError if there's no such template or a `<date>` doesn't follow a
    weekday, OSError or UnicodeDecodeError if the owner's template can't be read.
    """
    path = life_dir / TEMPLATES_DIR / f"week-{name}.md"
    if path.is_file():
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    elif name in DEFAULT_TEMPLATES:
        text = DEFAULT_TEMPLATES[name]
    else:
        raise TemplateError(f"no week template {path.name}")
    filled = WEEKDAY_PLACEHOLDER.sub(
        lambda match: f"{match[1]} {week.day(WEEKDAYS.index(match[1])).isoformat()}", text
    )
    if PLACEHOLDER in filled:
        raise TemplateError(f"{path.name} has a {PLACEHOLDER} that doesn't follow a weekday")
    return filled
