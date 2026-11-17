"""Run ids: `<YYYY-MM-DD>-<slug>`, with -2, -3, ... added on a clash."""

import re
import unicodedata
from datetime import date

SLUG_MAX_CHARS = 40
FALLBACK_SLUG = "run"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# What make_run_id can produce: lowercase alphanumeric words joined by single hyphens.
# Manifest.from_dict checks ids against it, since the id names the run folder.
RUN_ID_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


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
