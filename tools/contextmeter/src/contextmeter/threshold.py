"""The handoff threshold, read from AGENTS.md section 4 so there's one source of truth.

AGENTS.md says: hand off at "**N% of your context window**". This reads N, also when
setup has wrapped it in a marker: "**<!-- setting:context-handoff-percent -->N<!-- /setting -->%".
"""

import re
from pathlib import Path

DEFAULT_THRESHOLD_PCT = 75

# The optional <!-- setting:... --> markers are how setup (`setup config agents`) finds the value.
THRESHOLD_PATTERN = re.compile(
    r"\*\*(?:<!-- setting:context-handoff-percent -->)?(\d{1,3})(?:<!-- /setting -->)?"
    r"% of your context window\*\*"
)


def handoff_threshold(agents_md: Path) -> int:
    """Return the handoff percentage from `agents_md`, or 75 if it can't be read.

    A missing file, a missing line or a value outside 1-100 all fall back to the
    default: the hook must still warn even if AGENTS.md changes shape.
    """
    try:
        text = agents_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return DEFAULT_THRESHOLD_PCT
    match = THRESHOLD_PATTERN.search(text)
    if not match or not 1 <= int(match.group(1)) <= 100:
        return DEFAULT_THRESHOLD_PCT
    return int(match.group(1))
