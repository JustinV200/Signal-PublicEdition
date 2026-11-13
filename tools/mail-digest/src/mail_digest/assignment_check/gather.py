"""The check's first half: visit both sites, then run one reader per site.

The visits run one after the other, Classroom first, under the caller's run lock. A
launch that's busy (the checker's browser is open) or failed (no usable out file,
for example after the timeout kill) stops the check before any claude runs. Then one
tool-less reader per site that has ok pages, Moodle first; a reader that fails stops
the check too, so no writer runs on half a report.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from mail_digest.assignment_check.courses import (
    READ_ORDER,
    SITE_NAMES,
    VISIT_ORDER,
    CheckConfig,
    Page,
    site_pages,
)
from mail_digest.assignment_check.findings import SiteReading
from mail_digest.assignment_check.notices import BUSY, stopped_line
from mail_digest.assignment_check.reader import parse_reader, reader_context
from mail_digest.assignment_check.visit import LAUNCH_BUSY, LAUNCH_OK, PAGE_OK, SiteVisit
from mail_digest.claude import ClaudeRun

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Gathered:
    """Each site's reading, or the spoken line saying why the check stopped ("" if it didn't)."""

    sites: tuple[SiteReading, ...] = ()
    stopped: str = ""


@dataclass(frozen=True)
class GatherDeps:
    """visit(site, pages) runs one launch; read(argv, context) runs one reader claude;
    config holds the sites and courses."""

    config: CheckConfig
    visit: Callable[[str, tuple[Page, ...]], SiteVisit]
    read: Callable[[list[str], str], ClaudeRun]
    reader_argv: list[str]


def gather(deps: GatherDeps, now: datetime) -> Gathered:
    """Visit, then read (see the module docstring). Raises only on a bug."""
    visits = {}
    for site in VISIT_ORDER:
        visit = deps.visit(site, site_pages(site, deps.config))
        log.info(
            "%s visit: %s, pages %r", site, visit.status, [(p.key, p.status) for p in visit.pages]
        )
        if visit.status == LAUNCH_BUSY:
            return Gathered(stopped=BUSY)
        if visit.status != LAUNCH_OK:
            return Gathered(stopped=stopped_line(f"the {SITE_NAMES[site]} visit failed"))
        visits[site] = visit
    readings = []
    for site in READ_ORDER:
        reading = _read_site(deps, now, site, visits[site])
        if reading is None:
            return Gathered(stopped=stopped_line(f"the {SITE_NAMES[site]} reader failed"))
        readings.append(reading)
    return Gathered(sites=tuple(readings))


def _read_site(deps: GatherDeps, now: datetime, site: str, visit: SiteVisit) -> SiteReading | None:
    """One site's reading: the reader's report on its ok pages, or None if the reader failed.

    A site with no ok page runs no reader; findings/ then reports each page's status.
    """
    pages = site_pages(site, deps.config)
    texts = {page.key: page.text for page in visit.pages if page.status == PAGE_OK}
    ok_pages = [(page, texts[page.key]) for page in pages if page.key in texts]
    if not ok_pages:
        return SiteReading(pages, visit)
    context = reader_context(now, site, ok_pages)
    output = parse_reader(deps.read(deps.reader_argv, context.text))
    if output is None:
        return None
    return SiteReading(pages, visit, output, context.cut)
