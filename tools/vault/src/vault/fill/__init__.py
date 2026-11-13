"""Filling logins into Playwright pages, and keeping the filled values out of tool output."""

from vault.fill.deps import FillDeps
from vault.fill.redaction import REDACTION_MARK, page_has_filled_fields, scrub_text
from vault.fill.registry import FilledRegistry
from vault.fill.sequence import fill_login_with

__all__ = [
    "REDACTION_MARK",
    "FillDeps",
    "FilledRegistry",
    "fill_login_with",
    "page_has_filled_fields",
    "scrub_text",
]
