"""The error log, .state/errors.log, for the status line and hook.

Neither can report a failure where the owner sees it (the status line's stdout is
its display, and a hook must print nothing), so they append it here.
"""

from pathlib import Path

from usage.times import local_now, to_iso

# The status line runs every refresh in every session, so a lasting fault
# would grow the log forever. Past this size it starts over.
MAX_LOG_BYTES = 256 * 1024


def log_error(log_file: Path, source: str, error: BaseException) -> None:
    """Append one line with `error`'s type and message, raised in `source` (e.g. "hook").

    Only the type and message, never the repr: some reprs hold the input
    (a UnicodeDecodeError's holds the bytes it failed on), and hook input
    carries the last assistant message.

    Never raises: a failed log must not fail the status line or hook.
    """
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        is_full = log_file.exists() and log_file.stat().st_size > MAX_LOG_BYTES
        with log_file.open("w" if is_full else "a", encoding="utf-8", errors="replace") as handle:
            handle.write(f"{to_iso(local_now())} {source} {type(error).__name__}: {error}\n")
    except OSError:
        pass  # Nowhere left to report it; the caller must still finish.
