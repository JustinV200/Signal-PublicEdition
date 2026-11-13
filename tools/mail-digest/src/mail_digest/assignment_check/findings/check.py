"""The checks for one whole check: every site's pages, then their items, then the flags.

Pure: it reads nothing and writes nothing but the log. This is the boundary between
page text and life/ (design section 3.3); the writer only ever sees its output.
"""

from datetime import datetime

from mail_digest.assignment_check.findings.flags import flagged
from mail_digest.assignment_check.findings.items import checked_items
from mail_digest.assignment_check.findings.model import Findings
from mail_digest.assignment_check.findings.pages import SiteReading, usable_pages


def check_findings(sites: list[SiteReading], now: datetime) -> Findings:
    """The validated items and the page problems of every site. now is timezone-aware."""
    items, problems = [], []
    for site in sites:
        pages, site_problems = usable_pages(site)
        problems += site_problems
        if site.reading:
            items += checked_items(site.reading.items, pages)
    return Findings(items=flagged(items, now), problems=tuple(problems))
