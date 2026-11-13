"""Blank the values of password/OTP fields in an aria snapshot.

Playwright 1.64's aria snapshot prints input values verbatim, password fields
included (verified: `- textbox "Password" [ref=e7]: hunter2`). This module
rewrites such lines to `- textbox "Password" [ref=e7]: "[redacted]"` and drops
anything nested under them.

Redaction is decided by the underlying element, not the aria role: a page can
expose a password input as "button", "generic" or "slider". Every ref line that
shows a value or nested lines is checked live against the page by the
caller-supplied `is_sensitive`. Fail closed:
- a check that errors counts as sensitive;
- an element line without a ref has no element to check (ai mode gives refs only
  to interactable elements, so a zero-size or pointer-events:none password input
  has none), so any value it shows is redacted;
- an item line we can't parse is dropped.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from browser_tool.redaction.snapshot_lines import (
    SnapshotLine,
    indent_of,
    is_item_line,
    parse_line,
)

logger = logging.getLogger(__name__)

# No-ref lines that carry page text rather than an element's value.
TEXT_ROLES = frozenset({"text"})
REDACTED_VALUE = '"[redacted]"'
UNPARSED_LINE = '- "[unparsed line removed]"'

SensitivityCheck = Callable[[str], Awaitable[bool]]


def candidate_refs(lines: list[SnapshotLine | None]) -> list[str]:
    """Refs of lines that show a value or nested lines, whatever their role.

    A line whose only nested lines are `/url` properties (every link) shows no
    element value, since an href never comes from an <input>; it is skipped so a
    page of links doesn't cost two live checks per link.
    """
    return [
        line.ref
        for index, line in enumerate(lines)
        if line
        and line.ref
        and (line.has_value or (line.opens_children and not _only_url_children(lines, index)))
    ]


def _only_url_children(lines: list[SnapshotLine | None], index: int) -> bool:
    """True if every line nested under lines[index] is a parsed `/url` property."""
    parent = lines[index]
    children = 0
    for line in lines[index + 1 :]:
        if line is not None and line.indent <= parent.indent:
            break
        if line is None or line.role != "/url":
            return False  # an unparsed line counts as content (fail closed)
        children += 1
    return children > 0


def is_unverifiable_value(line: SnapshotLine) -> bool:
    """True for an element line with no ref (nothing to check) that shows a value."""
    is_property = line.role.startswith("/")  # e.g. "- /url: ..."
    return line.ref is None and line.has_value and line.role not in TEXT_ROLES and not is_property


async def redact_snapshot(text: str, is_sensitive: SensitivityCheck) -> str:
    """Return `text` with every sensitive field's value replaced by "[redacted]".

    Args:
        text: A Playwright aria snapshot in "ai" mode.
        is_sensitive: Async callback; given a ref, returns True for secret fields.

    Returns:
        The redacted snapshot. Refs and accessible names are kept.
    """
    raw_lines = text.splitlines()
    parsed = [parse_line(line) for line in raw_lines]
    refs = candidate_refs(parsed)
    verdicts = await asyncio.gather(*(_check_fail_closed(is_sensitive, ref) for ref in refs))
    sensitive_refs = {ref for ref, verdict in zip(refs, verdicts, strict=True) if verdict}
    return apply_redactions(raw_lines, parsed, sensitive_refs)


def apply_redactions(
    raw_lines: list[str], parsed: list[SnapshotLine | None], sensitive_refs: set[str]
) -> str:
    """Rewrite sensitive or unverifiable value lines and drop their nested lines (pure)."""
    output = []
    skip_deeper_than: int | None = None
    for raw, line in zip(raw_lines, parsed, strict=True):
        indent = indent_of(raw)
        if skip_deeper_than is not None:
            if indent > skip_deeper_than:
                continue
            skip_deeper_than = None
        if line is None:
            # An item line we couldn't parse might hide a value: drop it (fail closed).
            output.append(" " * indent + UNPARSED_LINE if is_item_line(raw) else raw)
            continue
        if line.ref in sensitive_refs or is_unverifiable_value(line):
            output.append(f"{' ' * line.indent}- {line.raw_key}: {REDACTED_VALUE}")
            skip_deeper_than = line.indent
            continue
        output.append(raw)
    return "\n".join(output)


async def _check_fail_closed(is_sensitive: SensitivityCheck, ref: str) -> bool:
    try:
        return await is_sensitive(ref)
    except Exception as error:  # noqa: BLE001 - any failure must mean "redact"
        logger.warning(
            "sensitivity check for ref %s failed (%s); redacting", ref, type(error).__name__
        )
        return True
