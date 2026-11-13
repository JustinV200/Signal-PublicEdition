"""The incoming folder: where Edge writes downloads while they are in flight.

Playwright's downloads_path makes Edge write each download as "<uuid>.crdownload"
while it runs and "<uuid>" when done. Playwright doesn't say how far a download
has got, so the size cap watches these files instead. The folder sits inside the
browser profile, which only one Edge can open, so no other browser shares it.
"""

import asyncio
import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

INCOMING_FOLDER_NAME = "signal-downloads-incoming"
# Edge deletes a cancelled download's partial file itself, a moment after the cancel.
PARTIAL_DELETE_WAIT_S = 5.0
PARTIAL_POLL_S = 0.1


def file_sizes(folder: Path) -> list[int]:
    """The size of each file in `folder` right now (empty when the folder is missing)."""
    sizes = []
    try:
        entries = list(folder.iterdir())
    except FileNotFoundError:
        return []
    for entry in entries:
        try:
            sizes.append(entry.stat().st_size)
        except FileNotFoundError:
            continue  # renamed or removed between the listing and the stat
    return sizes


async def remove_files_over(folder: Path, max_bytes: float) -> None:
    """After a cancel, make sure no file in `folder` over `max_bytes` stays.

    Waits up to PARTIAL_DELETE_WAIT_S for Edge to delete its partial file, then
    deletes what is left; a file that still can't be deleted is logged.
    """
    deadline = asyncio.get_running_loop().time() + PARTIAL_DELETE_WAIT_S
    while max(file_sizes(folder), default=0) > max_bytes:
        if asyncio.get_running_loop().time() >= deadline:
            _delete_files(folder, lambda entry: entry.stat().st_size > max_bytes)
            return
        await asyncio.sleep(PARTIAL_POLL_S)


def clear_folder(folder: Path) -> None:
    """Delete leftover files from a run that ended mid-download, before Edge starts.

    A leftover over the size cap would otherwise cancel every new download. A
    file that can't be deleted is logged and left. A folder that is a symlink or
    junction is left alone, so nothing outside the profile is ever cleared.
    """
    if folder.is_dir() and not folder.is_symlink() and not folder.is_junction():
        _delete_files(folder, lambda _entry: True)


def _delete_files(folder: Path, should_delete: Callable[[Path], bool]) -> None:
    """Delete the files in `folder` that `should_delete` picks; log the ones that won't go."""
    for entry in list(folder.iterdir()):
        try:
            if should_delete(entry):
                entry.unlink()
        except FileNotFoundError:
            continue  # already gone
        except OSError as error:
            logger.warning("could not delete a download file: %s", type(error).__name__)
