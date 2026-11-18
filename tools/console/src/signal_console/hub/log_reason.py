"""Why a voice hub quit while starting, in words fit for the owner's Chat.

The hub's log ends with the exception line of its traceback, which says what
failed. That line can hold local paths and be any length, so the home folder
becomes `~`, paths are cut to their last part and the line is capped; the full
log stays in .state/hub.log.
"""

import logging
import re
from pathlib import Path

from signal_console.paths import HUB_LOG_FILE

log = logging.getLogger(__name__)

# The longest log line Chat shows; past it the line ends in an ellipsis.
MAX_REASON_CHARS = 200
ELLIPSIS = "…"
# What may come before an absolute path's first separator: a drive or the home folder's `~`.
_PATH_ROOT = r"(?:[A-Za-z]:|~)?"
# A quoted path (how exceptions show one) up to its closing quote, spaces and all.
_QUOTED_PATH = re.compile(rf"(['\"])({_PATH_ROOT}[\\/].*?)\1")
# An unquoted path (not inside a word), its folders, then its last part (group 1,
# maybe empty). Repr-doubled backslashes count too. It never starts mid-run of
# separators, so a long run is tried once, not once per character (quadratic).
_PATH_TOKEN = re.compile(
    rf"(?<![\w.\\/]){_PATH_ROOT}[\\/]+(?:[^\s\"'\\/<>|]+[\\/]+)+([^\s\"'\\/<>|]*)"
)
_SEPARATORS = re.compile(r"[\\/]+")
# Where the home folder's name ends: not before more of a name (`someuser2`,
# `someuser-old`, `someuser.bak`), but before punctuation like `.`, `,`, `)` or `:`.
_NAME_ENDS = r"(?![\w-]|\.\w)"


def readable_line(line: str) -> str:
    """`line` with the home folder as `~`, each absolute path cut to its last part, and capped.

    Args:
        line: One line of the hub's log.

    Returns:
        The line, at most MAX_REASON_CHARS long (ending in an ellipsis when cut).
    """
    # The whole line is read (the patterns run in linear time) and only cut once
    # paths are gone, so a cut never leaves part of a folder's name.
    short = _without_home(line)
    short = _QUOTED_PATH.sub(lambda match: match[1] + _last_part(match[2]) + match[1], short)
    short = _PATH_TOKEN.sub(lambda match: match.group(1), short)
    if len(short) <= MAX_REASON_CHARS:
        return short
    return short[: MAX_REASON_CHARS - len(ELLIPSIS)] + ELLIPSIS


def _without_home(line: str) -> str:
    """`line` with the home folder (any separators: `\\`, repr-doubled, `/`, mixed) shown as `~`."""
    # `C:\Users\someuser` gives ["C:", "Users", "someuser"]; `/home/owner` gives
    # ["", "home", "owner"], so its pattern starts with a separator.
    parts = _SEPARATORS.split(str(Path.home()))
    pattern = r"[\\/]+".join(re.escape(part) for part in parts)
    # A home that starts with a separator matches only from a run's start, or a long
    # run would be tried once per character (quadratic).
    if not parts[0]:
        pattern = r"(?<![\\/])" + pattern
    # Case-blind, as Windows paths are.
    return re.sub(pattern + _NAME_ENDS, "~", line, flags=re.IGNORECASE)


def _last_part(path: str) -> str:
    """The last part of a path (empty when it ends in a separator)."""
    return _SEPARATORS.split(path)[-1]


def last_log_reason(state_dir: Path) -> str:
    """The end of `Voice quit while starting…`: the log's last line, or that it said nothing.

    Args:
        state_dir: The console's .state folder, which holds the hub's log.

    Returns:
        ` (<readable last line>). Try Start voice again.`, or
        `, without saying why. Try Start voice again.` when the log is empty or unreadable.
    """
    log_path = state_dir / HUB_LOG_FILE
    log.warning("voice hub exited while starting; its output is in %s", log_path)
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    # The exception line of a traceback is the log's last line: it says what failed.
    last = next((line.strip() for line in reversed(lines) if line.strip()), None)
    reason = f" ({readable_line(last)})" if last else ", without saying why"
    return f"{reason}. Try Start voice again."
