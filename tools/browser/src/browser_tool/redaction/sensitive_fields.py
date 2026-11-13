"""Playwright helpers built on the "signal-sensitive" selector engine.

register_sensitive_engine must run once per Playwright instance, right after the
browser context is opened (a CDP-connected default context only gets engines
registered once Playwright tracks it). The other helpers then ask the page whether a ref is
a secret field, or build screenshot masks for every frame.
"""

import logging

from playwright.async_api import Locator, Page, Playwright

from browser_tool.redaction.engine_script import (
    ENGINE_NAME,
    ENGINE_SCRIPT,
    FOCUSED_SENSITIVE_SELECTOR,
    SENSITIVE_SELECTOR,
)

logger = logging.getLogger(__name__)


async def register_sensitive_engine(playwright: Playwright) -> None:
    """Register the selector engine in Playwright's isolated (content-script) world.

    Raises:
        playwright.async_api.Error: If an engine with this name is already registered.
    """
    await playwright.selectors.register(ENGINE_NAME, ENGINE_SCRIPT, content_script=True)


async def is_sensitive_ref(page: Page, ref: str) -> bool:
    """Return True if the element behind an aria ref is a password/OTP-like field.

    Fails closed: a ref that no longer resolves counts as sensitive, because its
    value may already be in the snapshot text we are about to return.

    Args:
        page: The page the snapshot was taken from.
        ref: An aria ref such as "e7" or "f1e3".
    """
    target = page.get_by_ref(ref)
    if await is_sensitive_locator(page, target):
        return True  # one round trip for the common sensitive case
    if await target.count() == 0:
        logger.debug("ref %s no longer resolves; treating it as sensitive", ref)
        return True
    return False


async def is_sensitive_locator(page: Page, target: Locator) -> bool:
    """Return True if `target` (a single element) is a password/OTP-like field."""
    return await target.and_(page.locator(SENSITIVE_SELECTOR)).count() > 0


async def is_focus_on_sensitive_field(page: Page) -> bool:
    """Return True if the focused element, in any frame, is a password/OTP-like field."""
    for frame in page.frames:
        if await frame.locator(FOCUSED_SENSITIVE_SELECTOR).count() > 0:
            return True
    return False


def sensitive_masks(page: Page) -> list[Locator]:
    """Locators for every sensitive field in every frame, for screenshot(mask=...)."""
    return [frame.locator(SENSITIVE_SELECTOR) for frame in page.frames]
