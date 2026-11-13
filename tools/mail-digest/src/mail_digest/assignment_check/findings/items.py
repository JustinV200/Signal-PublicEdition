"""The per-item checks: the boundary between what the reader said and what reaches life/.

Each rule drops the item and logs it with %r, so page text can't forge log lines:
- page: one of this site's usable pages; the course comes from the runner's config;
- name: at most MAX_NAME_CHARS, safe for a KB line (kb.is_safe_text: no URLs, "]:",
  character references or 6+ digit numbers), and the exact quoted name of an element
  on that page (site_rules.is_named_on_page);
- ref: in the URL of the item's own link, in the expected shape (site_rules.item_link);
- class (Classroom): class_name is the course's class and is in the page's text;
- kind: one the reader schema allows; due: parses, or it's left empty.
Status comes from site_rules, never from the model. At most MAX_ITEMS_PER_PAGE per
page and MAX_ITEMS in all are kept.
"""

import logging
from datetime import datetime

from mail_digest.assignment_check.courses import CLASSROOM, Page
from mail_digest.assignment_check.findings.model import Item, fold
from mail_digest.assignment_check.findings.site_rules import (
    is_named_on_page,
    item_link,
    item_status,
)
from mail_digest.assignment_check.reader import ITEM_KINDS, ReaderItem
from mail_digest.kb import is_safe_text

log = logging.getLogger(__name__)

MAX_NAME_CHARS = 120
MAX_ITEMS_PER_PAGE = 60
MAX_ITEMS = 150
DUE_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d")


def checked_items(
    raw_items: tuple[ReaderItem, ...], pages: dict[str, tuple[Page, str]]
) -> list[Item]:
    """The items that pass every check, in the reader's order, capped (module docstring).

    pages: key -> (page, its text) for the usable pages (findings.pages).
    """
    folded = {key: fold(text) for key, (_page, text) in pages.items()}
    kept, per_page = [], dict.fromkeys(pages, 0)
    for raw in raw_items:
        if len(kept) >= MAX_ITEMS:
            log.warning("over %d items in all; dropping the rest", MAX_ITEMS)
            break
        item = _checked(raw, pages, folded)
        if item is None:
            continue
        if per_page[raw.page] >= MAX_ITEMS_PER_PAGE:
            log.warning("dropping %r: over %d items on %r", raw.name, MAX_ITEMS_PER_PAGE, raw.page)
            continue
        per_page[raw.page] += 1
        kept.append(item)
    return kept


def _checked(
    raw: ReaderItem, pages: dict[str, tuple[Page, str]], folded: dict[str, str]
) -> Item | None:
    """raw as a validated Item, or None (logged) if any check fails."""
    if raw.page not in pages:
        return _drop(raw, "not a usable page of this check")
    page, text = pages[raw.page]
    name = " ".join(raw.name.split())
    if not name or len(name) > MAX_NAME_CHARS or not is_safe_text(name):
        return _drop(raw, "a name that's empty, too long or has unsafe characters")
    if not is_named_on_page(name, folded[raw.page]):
        return _drop(raw, "a name that isn't on the page")
    if raw.kind not in ITEM_KINDS:
        return _drop(raw, "an unknown kind")
    if page.site == CLASSROOM and not _is_course_class(page, raw.class_name, folded[raw.page]):
        return _drop(raw, "a class that isn't the course's, or isn't on the page")
    link = item_link(page, name, raw.ref, text)
    if link is None:
        return _drop(raw, "a ref that isn't in the page's links")
    return Item(
        course=page.course.tag,
        site=page.site,
        name=name,
        kind=raw.kind,
        due=parse_due(raw.due),
        status=item_status(page, name, raw.ref, raw.status_text, text),
        link=link,
    )


def parse_due(due: str) -> str:
    """due in one of DUE_FORMATS, normalised, or "" if it doesn't parse."""
    for pattern in DUE_FORMATS:
        try:
            return datetime.strptime(due.strip(), pattern).strftime(pattern)
        except ValueError:
            continue
    return ""


def _is_course_class(page: Page, class_name: str, folded_text: str) -> bool:
    """True if class_name is page's course's class, and occurs in the page's text.

    The course's tag comes from courses.py through the page. If phase 0 moves to the
    /all lists, match against every Classroom course here instead.
    """
    wanted = fold(page.course.class_name)
    return bool(wanted) and fold(class_name) == wanted and wanted in folded_text


def _drop(raw: ReaderItem, why: str) -> None:
    """Log a dropped item with %r, and return None."""
    log.warning("dropping item %r on %r: %s", raw.name, raw.page, why)
    return None
