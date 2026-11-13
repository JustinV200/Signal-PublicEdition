"""Which of one site's pages can be used, and the problem with each one that can't.

A page is used only if the visit got it (ok), the reader got its whole text and marked
it readable, it isn't suspicious, and a Classroom page shows the school account
(checked here, in code: the reader's account field is only logged, and /u/N can
change). Any problem with one page leaves its whole course out of this check, so the
writer never concludes from part of a course that nothing is due.
"""

import logging
from dataclasses import dataclass

from mail_digest.assignment_check.courses import CLASSROOM, Page
from mail_digest.assignment_check.findings.model import (
    PAGE_ERROR,
    SUSPICIOUS,
    UNREADABLE,
    WRONG_ACCOUNT,
    Problem,
)
from mail_digest.assignment_check.reader import ReaderOutput
from mail_digest.assignment_check.visit import PAGE_OK, SiteVisit

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SiteReading:
    """Everything known about one site: its pages, the visit, and the reader's report.

    reading is None when no reader ran (no ok page). cut are the pages left out of
    the reader's context to stay under its cap.
    """

    pages: tuple[Page, ...]
    visit: SiteVisit
    reading: ReaderOutput | None = None
    cut: tuple[str, ...] = ()


def usable_pages(site: SiteReading) -> tuple[dict[str, tuple[Page, str]], tuple[Problem, ...]]:
    """(key -> (page, its text) for the pages to use; one Problem per page that can't be)."""
    visited = {page.key: page for page in site.visit.pages}
    good, problems = {}, []
    for page in site.pages:
        got = visited.get(page.key)
        reason = _problem(page, got.status if got else PAGE_ERROR, got.text if got else "", site)
        if reason:
            problems.append(Problem(page.course.tag, page.site, page.key, reason))
        else:
            good[page.key] = (page, got.text)
    if site.reading:
        log.info("reader's accounts for %s: %r", site.pages[0].site, site.reading.accounts)
    failed = {problem.course for problem in problems}
    if failed:
        log.warning("leaving %s out of this check: %r", sorted(failed), problems)
    usable = {k: v for k, v in good.items() if v[0].course.tag not in failed}
    return usable, tuple(problems)


def _problem(page: Page, status: str, text: str, site: SiteReading) -> str:
    """Why page can't be used ("" if it can)."""
    if status != PAGE_OK:
        return status
    reading = site.reading
    if reading is None or page.key in site.cut or page.key not in reading.readable:
        return UNREADABLE
    if page.key in reading.suspicious:
        return SUSPICIOUS
    if page.site == CLASSROOM and page.account not in text.casefold():
        return WRONG_ACCOUNT
    return ""
