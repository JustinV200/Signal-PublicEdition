"""Scrub the live values of secret fields out of any text before it leaves.

Element-based snapshot redaction misses values that reach text another way, for
example an accessible name built via aria-labelledby from a password input, or a
<label> that contains one. So every tool result is also searched for the current
value of every sensitive field in every frame, and each occurrence is replaced.
Values shorter than MIN_SECRET_CHARS are skipped (they would match everywhere).

Trade-off: this reads field values into this process for the comparison. They are
never logged or returned.

Each frame gets FRAME_READ_TIMEOUT_S: a frame that never answers (Edge's PDF
viewer did, and it froze every tool, since every result is scrubbed) raises
TimeoutError, which callers treat like any failed read: fail closed for that
call. Frames on the browser's own extension origin (the PDF viewer's) hold no
page fields and are skipped; every chrome-extension: frame is, including an
iframe another installed extension injects into a page.
"""

import asyncio
import contextlib
import json

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from browser_tool.redaction.engine_script import SENSITIVE_SELECTOR

MIN_SECRET_CHARS = 3
READ_ATTEMPTS = 3  # a navigation still committing destroys the frames being read
SETTLE_TIMEOUT_MS = 5_000
FRAME_READ_TIMEOUT_S = 2.0
# The browser's built-in pages inside a tab, such as the PDF viewer.
EXTENSION_SCHEME_PREFIX = "chrome-extension:"
REDACTED_TEXT = "[redacted]"
_VALUES_JS = "(els) => els.map((el) => typeof el.value === 'string' ? el.value : el.textContent)"


async def live_secret_values(page: Page) -> set[str]:
    """The live values of every sensitive field in every frame of `page`.

    A navigation still committing after an action (Enter submitting a form, a
    script redirect) destroys the frames mid-read, so on a Playwright error this
    waits for the new document and reads again, up to READ_ATTEMPTS times.

    Raises:
        playwright.async_api.Error: If every attempt fails (callers fail closed).
        TimeoutError: If a frame doesn't answer within FRAME_READ_TIMEOUT_S (not
            retried; callers fail closed).
    """
    for _ in range(READ_ATTEMPTS - 1):
        try:
            return await _read_values(page)
        except PlaywrightError:
            await _settle(page)
    return await _read_values(page)


async def _read_values(page: Page) -> set[str]:
    """One pass over the page's current frames, read together (any failure raises)."""
    frames = [
        frame
        for frame in page.frames
        if not frame.is_detached() and not frame.url.startswith(EXTENSION_SCHEME_PREFIX)
    ]
    found = await asyncio.gather(
        *(
            asyncio.wait_for(
                frame.locator(SENSITIVE_SELECTOR).evaluate_all(_VALUES_JS), FRAME_READ_TIMEOUT_S
            )
            for frame in frames
        )
    )
    return {value for values in found for value in values}


async def _settle(page: Page) -> None:
    """Wait (briefly) for a pending navigation's document; a timeout just retries."""
    with contextlib.suppress(PlaywrightError):
        await page.wait_for_load_state("domcontentloaded", timeout=SETTLE_TIMEOUT_MS)


def replace_values(text: str, values: set[str]) -> str:
    """Replace each value (and the forms a snapshot prints it in), longest first."""
    forms = {form for value in values if value for form in _printed_forms(value)}
    for form in sorted(forms, key=len, reverse=True):
        if len(form) >= MIN_SECRET_CHARS:
            text = text.replace(form, REDACTED_TEXT)
    return text


def _printed_forms(value: str) -> set[str]:
    """The value as typed, whitespace-collapsed, JSON-escaped (ASCII and not), and
    each of those YAML-'quoted' (a snapshot can JSON-escape a name inside a
    single-quoted key, e.g. `'button "mix: é''\\"77"'`)."""
    collapsed = " ".join(value.split())
    escaped = {json.dumps(collapsed, ensure_ascii=flag)[1:-1] for flag in (True, False)}
    forms = {collapsed, *escaped}
    return {value, *forms, *(form.replace("'", "''") for form in forms)}
