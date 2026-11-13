"""Log a hook's failure to .state/hook.log: a hook must never print, so this is its only outlet."""

from datetime import datetime
from pathlib import Path

from signal_console.paths import HOOK_LOG_FILE


def log_hook_failure(state_dir: Path, error: Exception) -> None:
    """Append one timestamped line for `error`; a failure to log is dropped (the hook exits 0)."""
    try:
        with (state_dir / HOOK_LOG_FILE).open("a", encoding="utf-8") as log_file:
            log_file.write(f"{datetime.now().isoformat(timespec='seconds')} {error!r}\n")
    except OSError:
        pass  # Nowhere left to report it; the hook must still exit 0.
