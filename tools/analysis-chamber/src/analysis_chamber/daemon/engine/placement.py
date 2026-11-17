"""Where a run folder may go: the checks before /start creates one, and the move at approval.

A new run is created under private_root only after its path passes the length
limit and the leak guard. At approval a non-personal run is renamed into
analyses_root in one atomic same-volume rename, so a failure can't leave a
partial copy under the repo (shutil.move would copy across volumes).
"""

import os
from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.daemon.engine.run_state import ChamberError
from analysis_chamber.guard import check_run_location
from analysis_chamber.runs import Manifest

# Longest run folder path. LongPathsEnabled=0 on this PC and the run's own venv
# (.venv/Lib/site-packages/...) and data/raw live inside it, so keep it short
# (orchestrator's budget from spike notes, not published).
MAX_RUN_DIR_CHARS = 100


def check_new_run(manifest: Manifest, config: ChamberConfig) -> Path:
    """The folder a new run will get under private_root, after checking it's allowed.

    Raises:
        ChamberError: The folder would be too long in either root.
        LeakError: private_root breaks the leak guard (e.g. it's inside the repo).
    """
    for root in (config.private_root, config.analyses_root):
        length = len(str(root / manifest.id))
        if length > MAX_RUN_DIR_CHARS:
            raise ChamberError(
                f"run folder {root / manifest.id} is {length} characters; the limit is "
                f"{MAX_RUN_DIR_CHARS} (Windows paths). Shorten the root in config.toml."
            )
    run_dir = config.private_root / manifest.id
    check_run_location(manifest, run_dir, config)
    return run_dir


def move_to_analyses(run_dir: Path, manifest: Manifest, config: ChamberConfig) -> Path:
    """Rename a non-personal run's folder into analyses_root.

    Args:
        run_dir: The run's folder under private_root.
        manifest: The run, with personal already False.
        config: For analyses_root and the leak guard.

    Returns:
        The new folder.

    Raises:
        LeakError: The destination breaks the leak guard (checked before anything moves).
        ChamberError: The roots are on different volumes, the destination exists,
            or the rename failed. The folder stays where it was.
    """
    destination = config.analyses_root / run_dir.name
    check_run_location(manifest, destination, config)
    if _volume(run_dir) != _volume(config.analyses_root):
        raise ChamberError(
            "private_root and analyses_root are on different volumes, so a run can't be "
            "moved atomically; put them on one drive in config.toml"
        )
    if destination.exists():
        raise ChamberError(f"{destination} already exists")
    try:
        config.analyses_root.mkdir(parents=True, exist_ok=True)
        run_dir.rename(destination)  # atomic on one volume; never copies
    except OSError as error:
        raise ChamberError(f"couldn't move run {manifest.id} to {destination}: {error}") from error
    return destination


def _volume(path: Path) -> str:
    return os.path.splitdrive(os.path.abspath(path))[0].casefold()
