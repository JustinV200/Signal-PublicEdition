"""A run folder's layout on disk: creating one and moving it between roots."""

import shutil
from pathlib import Path

RUN_SUBDIRS = ("data/raw", "data/clean", "extracts", "code", "figures", "models")
# Raw data, models and caches never get committed, even for non-personal runs.
RUN_GITIGNORE = "data/raw/\ndata/clean/\nmodels/\n.venv/\n__pycache__/\n.ipynb_checkpoints/\n"


def create_run_dir(root: Path, run_id: str) -> Path:
    """Make `<root>/<run_id>/` with its subfolders and .gitignore.

    Args:
        root: The run root (private_root for a new run).
        run_id: From make_run_id.

    Returns:
        The new run folder.

    Raises:
        FileExistsError: The folder already exists.
    """
    run_dir = root / run_id
    run_dir.mkdir(parents=True)
    for subdir in RUN_SUBDIRS:
        (run_dir / subdir).mkdir(parents=True)
    (run_dir / ".gitignore").write_text(RUN_GITIGNORE, encoding="utf-8")
    return run_dir


def move_run(run_dir: Path, dest_root: Path) -> Path:
    """Move a run folder into dest_root, keeping its name.

    Args:
        run_dir: The run folder.
        dest_root: The root to move it under (created if missing).

    Returns:
        The run's new folder.

    Raises:
        FileExistsError: dest_root already has a folder by that name.
        OSError: The move failed.
    """
    dest = dest_root / run_dir.name
    if dest.exists():
        raise FileExistsError(f"{dest} already exists")
    dest_root.mkdir(parents=True, exist_ok=True)
    # shutil.move copies then deletes across drives, and renames on the same drive.
    return Path(shutil.move(str(run_dir), str(dest)))
