"""Rolls life/ over to the week holding a given day: the rollover's one entry point.

If that week has no plan.md yet, it takes the newest earlier plan (across terms) and
creates, in the term pick_term chooses:

- weeks/<week>/workspace/README.md, log.md and review.md (from the templates);
- last week's review.md, filled by review.py, if it's missing or still blank;
- weeks/<week>/plan.md, from the template plus the carried todos, written last, so a
  crash part-way leaves no plan and the next run starts over.

A plan.md made early (by hand, say on the Sunday) has no carried note, so instead of
skipping the week, the carried todos it lacks are merged into it (status `merged`),
and the note is added so that happens once.

Catch-up: after a gap (the PC was off for weeks) it jumps straight to the current
week and carries everything from the last plan there. Empty in-between weeks would
hold nothing but the same carried list, and every reader looks at this week and next.

First week: with no earlier plan anywhere, start.py starts this week from the plan
template alone (status `started`), if life/inbox.md says life/ is in use.

Idempotent: a week whose plan.md has the carried note is left alone, and other
existing files are never overwritten (only a blank review is filled). Nothing is
ever ticked or deleted.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from mail_digest.rollover.carry import collect_carry
from mail_digest.rollover.plan_text import build_plan, has_carried_note, merge_plan, template_todos
from mail_digest.rollover.review import build_review, is_unfilled
from mail_digest.rollover.start import first_week_writes, uses_life, week_files
from mail_digest.rollover.templates import fill_template
from mail_digest.rollover.terms import pick_term
from mail_digest.rollover.weeks import (
    PLAN_FILE,
    Week,
    find_plan_dir,
    latest_plan_dir_before,
    week_from_folder,
    week_of,
)

log = logging.getLogger(__name__)

# Statuses: already rolled over, rolled over now, carried into an early plan, the
# first week started, nothing to carry from (and no first week), between terms.
CURRENT, ROLLED, MERGED, STARTED = "current", "rolled", "merged", "started"
NO_SOURCE, BETWEEN_TERMS = "no-source", "between-terms"


@dataclass(frozen=True)
class RolloverResult:
    """What a rollover did (or, on a dry run, would do).

    week: the target week's folder name. status: one of the statuses above.
    source: the plan carried from, relative to life/. carried, overdue: todo counts.
    writes: (path relative to life/, text) per file created or filled, in write order.
    """

    week: str
    status: str
    source: str | None = None
    carried: int = 0
    overdue: int = 0
    writes: tuple[tuple[str, str], ...] = field(default=())


@dataclass(frozen=True)
class Target:
    """The week being rolled into.

    folder: its week folder. week: the week. early_text: its early plan's text (one
    with no carried note, to merge into), or None for a new plan.
    """

    folder: Path
    week: Week
    early_text: str | None


def roll_over(life_dir: Path, today: date, dry_run: bool = False) -> RolloverResult:
    """Make sure today's week exists in life/ (see the module docstring).

    Raises TemplateError (a ValueError) for a broken template, OSError or
    UnicodeDecodeError for a file that can't be read or written.
    """
    week = week_of(today)
    early_dir = find_plan_dir(life_dir, week)
    early_text = (early_dir / PLAN_FILE).read_text(encoding="utf-8") if early_dir else None
    if early_text is not None and has_carried_note(early_text):
        return RolloverResult(week.name, CURRENT)
    source_dir = latest_plan_dir_before(life_dir, week)
    if source_dir is None:
        if early_dir:
            return RolloverResult(week.name, CURRENT)
        return _start_first_week(life_dir, week, dry_run)
    target_dir = early_dir or _new_week_dir(life_dir, source_dir, week)
    if target_dir is None:
        return RolloverResult(week.name, BETWEEN_TERMS, _relative(life_dir, source_dir / PLAN_FILE))
    result = _plan_writes(life_dir, source_dir, Target(target_dir, week, early_text), today)
    return _apply(life_dir, result, dry_run)


def _start_first_week(life_dir: Path, week: Week, dry_run: bool) -> RolloverResult:
    """Start the first week (start.py): no-source if life/ isn't used, or between terms."""
    if not uses_life(life_dir):
        return RolloverResult(week.name, NO_SOURCE)
    writes = first_week_writes(life_dir, week)
    if writes is None:
        return RolloverResult(week.name, BETWEEN_TERMS)
    relative = tuple((_relative(life_dir, p), t) for p, t in writes.items())
    return _apply(life_dir, RolloverResult(week.name, STARTED, writes=relative), dry_run)


def _apply(life_dir: Path, result: RolloverResult, dry_run: bool) -> RolloverResult:
    """Write result's files in order (none on a dry run) and return result."""
    if not dry_run:
        for relative, text in result.writes:
            _write(life_dir / relative, text)
            log.info("rollover wrote %s", relative)
    return result


def describe(result: RolloverResult) -> str:
    """One line on what a rollover did, for the log and the console."""
    if result.status not in (ROLLED, MERGED):
        return f"week {result.week}: {result.status}" + (
            f" (last plan {result.source})" if result.source else ""
        )
    return (
        f"week {result.week}: {result.status} from {result.source}, "
        f"{result.carried} todo(s) carried ({result.overdue} overdue), "
        f"{len(result.writes)} file(s)"
    )


def _new_week_dir(life_dir: Path, source_dir: Path, week: Week) -> Path | None:
    """The new week's folder in the term pick_term chooses, or None between terms."""
    term_dir = pick_term(life_dir, source_dir.parents[1], week)
    return term_dir / "weeks" / week.name if term_dir else None


def _plan_writes(life_dir: Path, source_dir: Path, target: Target, today: date) -> RolloverResult:
    """Work out every file to create or fill, without writing any.

    An early plan that already has every carried todo is left as it is (status
    current). A merge reports only the todos it added.
    """
    week, target_dir, early_text = target.week, target.folder, target.early_text
    source_week = week_from_folder(source_dir.name)
    plan_template = fill_template(life_dir, "plan", week)
    source_text = (source_dir / PLAN_FILE).read_text(encoding="utf-8")
    placeholders = template_todos(plan_template)
    carry = collect_carry(source_text, source_week.monday, today, placeholders)
    if early_text is None:
        plan_text, added = build_plan(plan_template, carry, source_week), carry
    else:
        plan_text, added = merge_plan(early_text, carry, source_week)
    if not added.count and early_text is not None:
        return RolloverResult(week.name, CURRENT)
    new_plan = target_dir / PLAN_FILE
    writes = week_files(life_dir, target_dir, week)
    old_review = source_dir / "review.md"
    if not old_review.exists() or is_unfilled(old_review.read_text(encoding="utf-8")):
        review_template = fill_template(life_dir, "review", source_week)
        writes[old_review] = build_review(
            review_template, carry, _relative(life_dir, new_plan), today
        )
    writes[new_plan] = plan_text
    return RolloverResult(
        week=week.name,
        status=ROLLED if early_text is None else MERGED,
        source=_relative(life_dir, source_dir / PLAN_FILE),
        carried=added.count,
        overdue=len(added.overdue),
        writes=tuple((_relative(life_dir, p), t) for p, t in writes.items()),
    )


def _write(path: Path, text: str) -> None:
    """Write text (UTF-8, LF) atomically, so a crash never leaves half a KB file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(text.encode("utf-8"))
    os.replace(temp, path)


def _relative(life_dir: Path, path: Path) -> str:
    """path relative to life/, in POSIX form."""
    return path.relative_to(life_dir).as_posix()
