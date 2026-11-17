"""The leak guard: where a run may live, and whether its report may be published.

Rules (spec 13): a personal run, or one whose flag the user hasn't set yet, never
sits inside the Signal repo. A non-personal run lives under analyses_root. Only
a non-personal run with the artifact format may be published.
"""

from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.runs import Manifest

ARTIFACT_FORMAT = "artifact"


class LeakError(Exception):
    """A run is stored where its personal flag forbids."""


def is_under(path: Path, root: Path) -> bool:
    """Whether path is root or inside it, after resolving links and `..`.

    WindowsPath compares case-insensitively, so `C:\\SIGNAL` is under `C:\\Signal`.
    """
    return path.resolve().is_relative_to(root.resolve())


def check_run_location(manifest: Manifest, run_dir: Path, config: ChamberConfig) -> None:
    """Refuse a run folder its personal flag doesn't allow.

    Args:
        manifest: The run (its personal flag).
        run_dir: Where the run folder is, or is about to be.
        config: For repo_root and analyses_root.

    Raises:
        LeakError: A personal or unflagged run is under repo_root or not under
            private_root, or a non-personal run isn't under analyses_root.
    """
    if manifest.personal is False:
        if not is_under(run_dir, config.analyses_root):
            raise LeakError(f"run {manifest.id}: non-personal runs must be under analyses_root")
        return
    if is_under(run_dir, config.repo_root):
        raise LeakError(f"run {manifest.id}: personal or unflagged run inside the Signal repo")
    if not is_under(run_dir, config.private_root):
        raise LeakError(f"run {manifest.id}: personal or unflagged runs must be under private_root")


def can_publish(manifest: Manifest) -> bool:
    """True only for a non-personal run whose report is an artifact."""
    return manifest.personal is False and manifest.report_format == ARTIFACT_FORMAT
