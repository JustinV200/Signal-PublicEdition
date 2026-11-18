"""Run ids. A new run gets an opaque id (`<YYYY-MM-DD>-p-<4 hex>`) so a personal question's
words never reach a folder name, log line or notice; a run approved as non-personal is
renamed to a readable `<YYYY-MM-DD>-<slug>` (with -2, -3, ... on a clash)."""

import re
import secrets
import unicodedata
from datetime import date

SLUG_MAX_CHARS = 40
FALLBACK_SLUG = "run"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# What make_run_id can produce: lowercase alphanumeric words joined by single hyphens.
# Manifest.from_dict checks ids against it, since the id names the run folder.
RUN_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
OPAQUE_MARKER = "p"  # every run starts as if personal: the flag isn't known until approval
OPAQUE_HEX_BYTES = 2  # 4 hex characters

_OPAQUE_ID = re.compile(rf"\d{{4}}-\d\d-\d\d-{OPAQUE_MARKER}-[0-9a-f]{{{OPAQUE_HEX_BYTES * 2}}}")


def is_opaque_id(name: str) -> bool:
    """Whether `name` has the shape make_opaque_id produces."""
    return _OPAQUE_ID.fullmatch(name) is not None


def make_opaque_id(today: date, taken: set[str]) -> str:
    """A new random run id, `<YYYY-MM-DD>-p-<4 hex>`, that isn't in `taken`.

    Args:
        today: The date prefix.
        taken: Ids already in use (both run roots).

    Returns:
        An id containing no words from the question.
    """
    while True:
        run_id = f"{today.isoformat()}-{OPAQUE_MARKER}-{secrets.token_hex(OPAQUE_HEX_BYTES)}"
        if run_id not in taken:
            return run_id


def make_run_id(question: str, today: date, taken: set[str]) -> str:
    """A new run id for the question that isn't in `taken`.

    Args:
        question: The user's question; its words become the slug.
        today: The date prefix.
        taken: Ids already in use (both run roots).

    Returns:
        `<YYYY-MM-DD>-<slug>`, or that plus `-2`, `-3`, ... if it's taken.
    """
    base = f"{today.isoformat()}-{_slugify(question)}"
    run_id, suffix = base, 2
    while run_id in taken:
        run_id = f"{base}-{suffix}"
        suffix += 1
    return run_id


def _slugify(text: str) -> str:
    """Lowercase ASCII words joined by hyphens, at most SLUG_MAX_CHARS long."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = _NON_ALNUM.sub("-", ascii_text.lower()).strip("-")
    # Cut at the limit, then drop a trailing hyphen the cut may leave.
    return slug[:SLUG_MAX_CHARS].rstrip("-") or FALLBACK_SLUG
