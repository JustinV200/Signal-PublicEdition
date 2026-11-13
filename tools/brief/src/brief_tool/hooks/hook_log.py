"""hook.log: one line per prompt with the session id, decision and timings, never prompt text.

The log starts over past 256 KiB. Every value is cleaned to a short token first, so
nothing from the hook's input beyond the session id can reach it.
"""

import re
import sys
from pathlib import Path

from signal_brief import local_now, to_iso

MAX_LOG_BYTES = 256 * 1024
# Keeps "," and "=" so a decision like "full,acked=1" reads as written; no spaces.
UNSAFE = re.compile(r"[^A-Za-z0-9_.:,=-]")
MAX_VALUE_CHARS = 64


def log_hook_run(path: Path, fields: dict[str, object]) -> None:
    """Append one `key=value` line. Never raises: a hook's log must not fail its prompt."""
    line = " ".join(
        [to_iso(local_now())] + [f"{key}={_clean(value)}" for key, value in fields.items()]
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        too_big = path.exists() and path.stat().st_size > MAX_LOG_BYTES
        with path.open("w" if too_big else "a", encoding="utf-8") as log_file:
            log_file.write(f"{line}\n")
    except OSError as error:
        # Claude Code keeps a hook's stderr in its debug log; the prompt still goes through.
        sys.stderr.write(f"brief hook: can't write {path.name}: {type(error).__name__}\n")


def _clean(value: object) -> str:
    return UNSAFE.sub("_", str(value))[:MAX_VALUE_CHARS]
