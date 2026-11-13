"""Parses the reader's structured output into plain, shape-checked values.

Only the shape is checked here (strings, a boolean, caps on counts and lengths); every
value is still the model's, which read untrusted pages. findings/ decides what to
believe, against the visit's own page text.
"""

import logging
from dataclasses import dataclass

from mail_digest.claude import ClaudeRun, structured_output

log = logging.getLogger(__name__)

# Caps on what's parsed at all; findings/ applies the real per-page and total caps.
MAX_RAW_ITEMS = 500
MAX_RAW_PAGES = 50
# Longer strings are cut here; a cut name then fails findings/' page-text check.
MAX_FIELD_CHARS = 300
ITEM_FIELDS = ("page", "name", "class_name", "kind", "due", "status_text", "ref")


@dataclass(frozen=True)
class ReaderItem:
    """One item as the reader reported it (see refdocs/routines/assignment-check-reader.md)."""

    page: str
    name: str
    class_name: str
    kind: str
    due: str
    status_text: str
    ref: str


@dataclass(frozen=True)
class ReaderOutput:
    """The reader's report on one site.

    readable: keys of the pages it marked readable (an unlisted page isn't).
    accounts: page key -> the account it says the page shows (only logged).
    suspicious: keys of the pages it says had text aimed at an assistant.
    """

    readable: frozenset[str]
    accounts: dict[str, str]
    items: tuple[ReaderItem, ...]
    suspicious: frozenset[str]


def parse_reader(run: ClaudeRun) -> ReaderOutput | None:
    """The reader's output, or None if the run failed or its output is malformed (logged)."""
    output, error = structured_output(run)
    if output is None:
        log.error("the reader failed: %s", error)
        return None
    pages, items, suspicious = (output.get(k) for k in ("pages", "items", "suspicious"))
    if not all(isinstance(value, list) for value in (pages, items, suspicious)):
        log.error("the reader's output is malformed")
        return None
    pages = [p for p in pages[:MAX_RAW_PAGES] if isinstance(p, dict)]
    return ReaderOutput(
        readable=frozenset(_text(p.get("key")) for p in pages if p.get("readable") is True),
        accounts={_text(p.get("key")): _text(p.get("account")) for p in pages},
        items=tuple(_item(item) for item in items[:MAX_RAW_ITEMS] if _is_item(item)),
        suspicious=frozenset(_text(key) for key in suspicious[:MAX_RAW_PAGES]),
    )


def _is_item(item: object) -> bool:
    """True if item is an object whose fields are all strings."""
    return isinstance(item, dict) and all(isinstance(item.get(f), str) for f in ITEM_FIELDS)


def _item(item: dict) -> ReaderItem:
    """One shape-checked item, every field cut to MAX_FIELD_CHARS."""
    return ReaderItem(**{field: item[field][:MAX_FIELD_CHARS] for field in ITEM_FIELDS})


def _text(value: object) -> str:
    """value if it's a string (cut to MAX_FIELD_CHARS), else ""."""
    return value[:MAX_FIELD_CHARS] if isinstance(value, str) else ""
