"""`assignment-check --sign-in-test`: open each site's first page once, to prove the sign-in works.

Setup runs it after you enter your school's sites. It visits one page per site with
the same browser-tool-visit launch a real check uses (so the same allowlist, the one
vault fill on the SSO host, and Duo, which only you approve on your phone), and
prints each site's status. No model runs and nothing in life/ changes.
"""

from collections.abc import Callable

from mail_digest.assignment_check.courses import (
    SITE_NAMES,
    VISIT_ORDER,
    CheckConfig,
    Page,
    site_pages,
)
from mail_digest.assignment_check.visit import LAUNCH_OK, PAGE_OK, SiteVisit, visit_site


def sign_in_test(
    config: CheckConfig, visit: Callable[[str, tuple[Page, ...]], SiteVisit] = visit_site
) -> tuple[bool, list[str]]:
    """(every used site opened its first page, one line per site). Never raises."""
    lines, is_ok = [], True
    for site in VISIT_ORDER:
        pages = site_pages(site, config)[:1]
        if not pages:
            continue
        result = visit(site, pages)
        status = result.pages[0].status if result.pages else result.status
        is_site_ok = result.status == LAUNCH_OK and status == PAGE_OK
        is_ok = is_ok and is_site_ok
        lines.append(f"{SITE_NAMES[site]}: {'signed in' if is_site_ok else status}")
    return is_ok, lines or ["No courses configured."]
