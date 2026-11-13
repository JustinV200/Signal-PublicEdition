"""Read the complete new lines of a growing log file (the hub's hub.log) on each call."""

from pathlib import Path


class LogTail:
    """Remembers how far a log file has been read; a partial last line waits for its newline."""

    def __init__(self, path: Path) -> None:
        """Start at the beginning of `path` (it may not exist yet)."""
        self._path = path
        self._offset = 0

    def reset(self) -> None:
        """Read from the start again (the file was replaced by a new hub's log)."""
        self._offset = 0

    def read_new_lines(self) -> list[str]:
        """The complete lines added since the last call (none if the file is missing).

        A file shorter than what was already read was truncated, so it's read
        from the start again.
        """
        try:
            with self._path.open("rb") as log_file:
                size = log_file.seek(0, 2)
                if size < self._offset:
                    self._offset = 0
                log_file.seek(self._offset)
                chunk = log_file.read(size - self._offset)
        except FileNotFoundError:
            return []
        complete = chunk[: chunk.rfind(b"\n") + 1]
        self._offset += len(complete)
        return complete.decode("utf-8", errors="replace").splitlines()
