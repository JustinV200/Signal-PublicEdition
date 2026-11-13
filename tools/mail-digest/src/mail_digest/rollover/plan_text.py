"""Builds the new week's plan.md: the filled template plus what was carried over.

The template's sections come first, in its order, each with its carried todos
appended. Sections only last week's plan had (`## Errands`, say) follow, in that
plan's order. A note under the title says where the carried todos came from, as the
hand-made plans did. That note also marks a plan as carried into: a plan made early
(by hand, before Monday) lacks it, so merge_plan adds the missing todos to it once.
"""

import re

from mail_digest.deadlines import open_todos
from mail_digest.rollover.carry import OPEN_TODO, OVERDUE, Carry
from mail_digest.rollover.sections import WeekFile, join_sections, split_sections
from mail_digest.rollover.weeks import Week

CARRIED_NOTE = (
    "Due format: `(due YYYY-MM-DD HH:MM)`, 24-hour clock. "
    '"carried" = moved over from the {source} week, not confirmed done.'
)
# Found in every plan carried into, by hand or by code.
CARRIED_NOTE_MARK = '"carried" = moved over from the'
# A ticked todo, read as open so it counts as present when merging (never re-opened).
TICKED_BOX = re.compile(r"^(\s*[-*+] )\[[xX]\]", re.MULTILINE)


def template_todos(template_text: str) -> frozenset[str]:
    """The template's own open todo lines, stripped (placeholders like "fill from backlog")."""
    return frozenset(line.strip() for line in template_text.splitlines() if OPEN_TODO.match(line))


def has_carried_note(plan_text: str) -> bool:
    """True if the plan has already been carried into (it has the carried note)."""
    return CARRIED_NOTE_MARK in plan_text


def build_plan(template_text: str, carry: Carry, source: Week) -> str:
    """The new plan.md text (LF), from the filled template, the carry and the source week."""
    plan = split_sections(template_text)
    _add_carry(plan, carry, source)
    return join_sections(plan)


def merge_plan(plan_text: str, carry: Carry, source: Week) -> tuple[str, Carry]:
    """An early plan (no carried note) with the carried todos it lacks, and the note.

    A todo counts as present if the plan has one, open or ticked, with the same tag
    and name (notes and due markers aside), so nothing the owner ticked is re-opened.
    Returns the merged text and the part of carry that was actually added.
    """
    present = {(t.tag, t.name) for t in open_todos(TICKED_BOX.sub(r"\1[ ]", plan_text))}
    missing = [
        item
        for item in carry.items
        if not any((t.tag, t.name) in present for t in open_todos(item.split("\n", 1)[0]))
    ]
    kept = Carry(
        overdue=tuple(i for i in carry.overdue if i in missing),
        by_section=tuple(
            (heading, tuple(i for i in items if i in missing))
            for heading, items in carry.by_section
        ),
        done=carry.done,
    )
    plan = split_sections(plan_text)
    _add_carry(plan, kept, source)
    return join_sections(plan), kept


def _add_carry(plan: WeekFile, carry: Carry, source: Week) -> None:
    """Add the carried note under the title and each carried todo to its section.

    A plan without `## Overdue` gets it as its first section, and only if it has items.
    """
    plan.preamble += ["", CARRIED_NOTE.format(source=source.monday.isoformat())]
    if carry.overdue:
        plan.ensure_section(OVERDUE, is_first=True).lines.extend(carry.overdue)
    for heading, items in carry.by_section:
        if items:
            plan.ensure_section(heading).lines.extend(items)
