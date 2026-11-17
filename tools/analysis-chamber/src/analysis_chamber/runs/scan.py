"""Find every run by scanning the run roots for manifest.json (there's no separate index)."""

import logging
from pathlib import Path

from analysis_chamber.runs.manifest import Manifest, ManifestError
from analysis_chamber.runs.store import MANIFEST_NAME, read_manifest

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
            if manifest.id != run_dir.name:
                log.warning("skipping run %s: manifest id is %r", run_dir, manifest.id)
                continue
            found.append((run_dir, manifest))
    return found
