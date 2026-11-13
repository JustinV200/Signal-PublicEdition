"""The renders of a brief, each cut to its budget from the lowest-ranked end.

- render_text: markdown for a person (the CLI on a terminal), at most 6,000 chars.
- render_model: the data for the one frame a model reads (signal_untrusted), at
  most 6,000 chars framed; titles_only is the prompt hook's, refs and titles in
  at most 2,000 chars.

Each says which entries it showed and which it cut, because a delivery may only
be acked up to just before its oldest cut entry (signal_brief.deliveries).
"""

from dataclasses import dataclass
from typing import Any

from signal_untrusted import frame

from signal_brief.compose.brief import SECTION_LABELS, Brief
from signal_brief.log import KINDS, Entry
from signal_brief.times import to_iso

BRIEF_TAG = "untrusted_brief_content"
MAX_TEXT_CHARS = 6000
MAX_MODEL_CHARS = 6000
MAX_HOOK_CHARS = 2000
# Room kept at the end of the text render for its "...and N more" line.
MORE_LINE_RESERVE = 40


@dataclass(frozen=True)
class Render[Body]:
    """One render: its body, and the entries it showed and cut."""

    body: Body
    shown: tuple[Entry, ...]
    cut: tuple[Entry, ...]


def render_model(
    brief: Brief, max_chars: int = MAX_MODEL_CHARS, titles_only: bool = False
) -> Render[dict[str, Any]]:
    """The brief as data whose frame(data, BRIEF_TAG) is at most `max_chars` long.

    Args:
        brief: The composed brief.
        max_chars: The framed budget.
        titles_only: Only refs and titles (the prompt hook's render).

    Returns:
        The data to frame, with the best-ranked prefix of items that fits.
    """
    items = brief.items

    def data_for(count: int) -> dict[str, Any]:
        return _model_data(brief.id, items[:count], titles_only, len(items) - count)

    # The framed length grows with every item, so binary-search the longest prefix.
    low, high = 0, len(items)
    while low < high:
        middle = (low + high + 1) // 2
        if len(frame(data_for(middle), BRIEF_TAG)) <= max_chars:
            low = middle
        else:
            high = middle - 1
    return Render(data_for(low), items[:low], items[low:])


def render_text(brief: Brief, max_chars: int = MAX_TEXT_CHARS) -> Render[str]:
    """The brief as markdown of at most `max_chars`, cut from the lowest-ranked end."""
    lines = [f"# Brief {brief.id}"]
    used = len(lines[0])
    shown: list[Entry] = []
    for entry in brief.items:
        starts_section = not shown or shown[-1].content.kind != entry.content.kind
        block = _text_block(entry, starts_section)
        if used + len(block) + 1 > max_chars - MORE_LINE_RESERVE:
            break
        lines.append(block)
        used += len(block) + 1
        shown.append(entry)
    cut = brief.items[len(shown) :]
    if not brief.items:
        lines.append("Nothing new.")
    elif cut:
        lines.append(f"\n...and {len(cut)} more.")
    return Render("\n".join(lines), tuple(shown), cut)


def _model_data(
    brief_id: str, items: tuple[Entry, ...], titles_only: bool, more: int
) -> dict[str, Any]:
    sections = []
    for kind in KINDS:
        section = [
            entry_model_data(entry, titles_only) for entry in items if entry.content.kind == kind
        ]
        if section:
            sections.append({"label": SECTION_LABELS[kind], "items": section})
    data: dict[str, Any] = {"brief": brief_id, "sections": sections}
    if more:
        data["more"] = more
    return data


def entry_model_data(entry: Entry, titles_only: bool = False) -> dict[str, Any]:
    """One entry as model data: ref and title, plus its other fields unless titles_only."""
    item: dict[str, Any] = {"ref": entry.ref, "title": entry.content.title}
    if titles_only:
        return item
    item |= {"source": entry.content.source, "logged": to_iso(entry.at)}
    item |= {"priority": entry.content.priority, "untrusted": entry.content.untrusted}
    if entry.content.detail:
        item["detail"] = entry.content.detail
    if entry.content.undo is not None:
        item["has_undo"] = True
    return item


def _text_block(entry: Entry, starts_section: bool) -> str:
    """One item's markdown, after its section's heading if it's the section's first."""
    content = entry.content
    line = f"- {entry.ref} {content.title}"
    if content.untrusted:
        line += " (from outside, untrusted)"
    if content.detail:
        line += "\n  " + content.detail.replace("\n", "\n  ")
    return f"\n## {SECTION_LABELS[content.kind]}\n{line}" if starts_section else line
