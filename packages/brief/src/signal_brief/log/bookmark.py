"""bookmark.json: `through`, the newest seq the owner has seen. It only moves forward."""

from signal_brief.paths import BriefPaths
from signal_brief.store import read_json_object, write_json_atomic


def read_through(paths: BriefPaths) -> int:
    """The bookmark's `through` (0 before any ack). Raises BriefLogError if unreadable."""
    through = read_json_object(paths.bookmark).get("through")
    return through if isinstance(through, int) and through >= 0 else 0


def advance_through_locked(paths: BriefPaths, through: int) -> int:
    """Move the bookmark to max(old, through). Call under the log's lock.

    Returns:
        The bookmark after the move.

    Raises:
        BriefLogError: bookmark.json couldn't be read or written.
    """
    old = read_through(paths)
    if through <= old:
        return old
    write_json_atomic(paths.bookmark, {"through": through})
    return through
