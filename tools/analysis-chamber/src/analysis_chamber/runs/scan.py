"""Find every run by scanning the run roots for manifest.json (there's no separate index)."""

import logging
from pathlib import Path

from analysis_chamber.runs.ids import is_opaque_id
from analysis_chamber.runs.manifest import Manifest, ManifestError
from analysis_chamber.runs.states import Status
from analysis_chamber.runs.store import MANIFEST_NAME, read_manifest, write_manifest

log = logging.getLogger(__name__)


def scan_runs(roots: list[Path]) -> list[tuple[Path, Manifest]]:
    """Every readable run one level under each root.

    A missing root is skipped (nothing has been created there yet). A run whose
    manifest can't be read, or whose id isn't its folder name, is skipped with a
    warning, so one bad file can't hide the rest.

    Args:
        roots: Run roots, usually [analyses_root, private_root].

    Returns:
        (run folder, manifest) pairs, sorted by folder name within each root.
    """
    found: list[tuple[Path, Manifest]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for run_dir in sorted(root.iterdir()):
            if not (run_dir / MANIFEST_NAME).is_file():
                continue
            try:
                manifest = read_manifest(run_dir)
            except ManifestError as error:
                log.warning("skipping run %s: %s", run_dir, error)
                continue
            # The folder name is the id; a mismatch means a hand-copied or renamed run.
            if manifest.id != run_dir.name and _is_rolled_back(run_dir, manifest):
                try:
                    manifest = write_manifest(run_dir, manifest)
                except ManifestError as error:
                    log.warning("skipping run %s: %s", run_dir, error)
                    continue
            elif manifest.id != run_dir.name:
                log.warning("skipping run %s: manifest id is %r", run_dir, manifest.id)
                continue
            found.append((run_dir, manifest))
    return found


def _is_rolled_back(run_dir: Path, manifest: Manifest) -> bool:
    """Whether a crash hit between a non-personal approval's manifest write and its rename.

    The folder is still opaque and the run unapproved, so restore the state `_place` rolls
    back to: the opaque id and personal unset (the leak guard refuses a non-personal run
    under private_root). Changes `manifest` in place.
    """
    if not (is_opaque_id(run_dir.name) and manifest.status is Status.AWAITING_APPROVAL):
        return False
    log.warning("run %s: manifest id %r reset to the folder's opaque id", run_dir, manifest.id)
    manifest.id, manifest.personal = run_dir.name, None
    return True
