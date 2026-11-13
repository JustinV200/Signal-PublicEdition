"""Playwright errors are reduced to fixed reasons that never echo their message."""

import pytest
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser_tool.actions import describe_playwright_error

SECRET = "hunter2-should-never-show"


def test_call_log_with_fill_value_is_not_echoed():
    error = PlaywrightError(
        f'Locator.fill: element is not editable\nCall log:\n  - fill("{SECRET}")'
    )
    assert describe_playwright_error(error) == "the element is not editable"
    assert describe_playwright_error(PlaywrightError(SECRET)) == "the browser action failed"


def test_network_error_code_is_the_only_thing_copied():
    error = PlaywrightError(f"Page.goto: net::ERR_NAME_NOT_RESOLVED at http://x/?q={SECRET}")
    assert describe_playwright_error(error) == "network error net::ERR_NAME_NOT_RESOLVED"


@pytest.mark.parametrize(
    ("cause", "reason"),
    [
        (f'<div title="{SECRET}">x</div> intercepts pointer events', "another element"),
        ("element is not stable", "still moving"),
        ("Element is not an <input>, <textarea> or [contenteditable] element", "not a text field"),
        ("waiting for locator", "timed out"),
    ],
)
def test_timeouts_name_their_cause(cause, reason):
    error = PlaywrightTimeoutError(f"Locator.click: Timeout 5000ms exceeded.\n  - {cause}")
    described = describe_playwright_error(error)
    assert reason in described
    assert SECRET not in described
