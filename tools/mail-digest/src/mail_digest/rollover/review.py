"""Fills last week's review.md with what the rollover knows for certain.

Done gets the ticked todos, Carried over the counts, where they went and the todos
carried STALE_WEEKS or more weeks (from their `carried from` mark), and Notes
says the rollover was automatic. Slipped and any prose are left for an agent or the
owner. A review that already has any content is never touched.
"""

from datetime import date

from mail_digest.rollover.carry import OPEN_TODO, STALE_WEEKS, TICKED_TODO, Carry
from mail_digest.rollover.sections import SECTION_PREFIX, join_sections, split_sections

DONE = "## Done"
CARRIED_OVER = "## Carried over"
NOTES = "## Notes"


def is_unfilled(review_text: str) -> bool:
    """True if the review has nothing but its title, headings and blank lines."""
    lines = review_text.splitlines()[1:]
    return all(not line.strip() or line.startswith(SECTION_PREFIX) for line in lines)


def build_review(template_text: str, carry: Carry, new_plan: str, today: date) -> str:
    """Last week's review (LF) from its filled template.

    new_plan: the new plan's path relative to life/, which the carried todos went to.
    """
    review = split_sections(template_text)
    done = [f"  - {TICKED_TODO.sub('', line, count=1)}" for line in carry.done]
    review.ensure_section(DONE).lines.extend(
        [f"- {len(carry.done)} todo(s) ticked in plan.md:", *done]
    )
    carried_over = review.ensure_section(CARRIED_OVER).lines
    carried_over.append(
        f"- {carry.count} open todo(s) moved to {new_plan} and marked carried, "
        f"{len(carry.overdue)} of them under Overdue."
    )
    if carry.stale:
        carried_over.append(f"- Carried {STALE_WEEKS} or more weeks:")
        carried_over += [f"  - {OPEN_TODO.sub('', line, count=1)}" for line in carry.stale]
    review.ensure_section(NOTES).lines.append(
        f"- Rolled over automatically on {today.isoformat()}; Slipped and Notes still to write."
    )
    return join_sections(review)
