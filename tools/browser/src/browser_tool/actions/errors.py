"""Errors that actions raise, and safe descriptions of Playwright failures.

Raw Playwright exception text must never reach the model or the logs: its call
logs can contain fill("<value>") with the very text that was typed. Playwright
errors are mapped to a fixed reason picked by a known substring of the message
(timeouts included); only a fixed net::ERR_* code is ever copied out of it.
"""

import re

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

# Defined below the subpackages so the session can raise one too; re-exported here.
from browser_tool.errors import ActionError

__all__ = ["ActionError", "describe_playwright_error"]

_NET_ERROR_RE = re.compile(r"net::ERR_[A-Z_]+")
GENERIC_FAILURE = "the browser action failed"
TIMEOUT_FAILURE = "timed out waiting for the page or element"

# (substring of the Playwright message, safe description). First match wins.
# Timeouts are checked against these too: an actionability wait that runs out
# names its cause (a covering overlay, a moving element) in the message.
_KNOWN_PROBLEMS = (
    (
        "intercepts pointer events",
        "another element (a dialog, banner or overlay) covers it; close it or take a new snapshot",
    ),
    ("element is not stable", "the element is still moving or animating; try again"),
    ("not an <input>, <textarea>", "the element is not a text field"),
    ("has been closed", "the page or browser was closed"),
    ("strict mode violation", "the ref matched several elements; take a new snapshot"),
    ("not attached", "the element is no longer on the page; take a new snapshot"),
    ("detached", "the element is no longer on the page; take a new snapshot"),
    ("not visible", "the element is not visible"),
    ("not enabled", "the element is disabled"),
    ("not editable", "the element is not editable"),
    ("Unknown key", "unknown key name"),
    ("did not find some options", "no such option in that list"),
)


def describe_playwright_error(error: Exception) -> str:
    """Map a Playwright exception to a short reason that contains no page data.

    Args:
        error: Any exception raised by a Playwright call.

    Returns:
        A fixed description, or "network error net::ERR_..." for network failures.
    """
    message = str(error)
    is_timeout = isinstance(error, PlaywrightTimeoutError)
    network_error = None if is_timeout else _NET_ERROR_RE.search(message)
    if network_error:
        return f"network error {network_error.group(0)}"
    for needle, description in _KNOWN_PROBLEMS:
        if needle in message:
            return description
    return TIMEOUT_FAILURE if is_timeout else GENERIC_FAILURE
