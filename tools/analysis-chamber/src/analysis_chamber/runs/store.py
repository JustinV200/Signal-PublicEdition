"""Read and write a run folder's manifest.json.

Writes go through signal_jsonstate (temp file + os.replace), so a reader never
sees half a file. Its temp name is per process, so within the daemon only one
task may write a given run's manifest at a time (the run's own pipeline task).
"""

import json
from dataclasses import replace
from pathlib import Path

from signal_jsonstate import StateFileError, read_bytes_retrying, write_json_atomic

from analysis_chamber.runs.manifest import Manifest, ManifestError, utc_now_iso

MANIFEST_NAME = "manifest.json"


def read_manifest(run_dir: Path) -> Manifest:
    """The run's manifest.

    Args:
        run_dir: The run folder.

    Returns:
        The parsed, validated manifest.

    Raises:
        ManifestError: It's missing, unreadable, not JSON or fails Manifest.from_dict.
    """
    path = run_dir / MANIFEST_NAME
    try:
        data = json.loads(read_bytes_retrying(path))
    except (OSError, ValueError, RecursionError) as error:
        raise ManifestError(f"can't read {path}: {error}") from error
    return Manifest.from_dict(data)


def write_manifest(run_dir: Path, manifest: Manifest) -> Manifest:
    """Write the manifest atomically with updated_at set to now.

    Args:
        run_dir: The run folder (must exist).
        manifest: The record to save; it isn't changed.

    Returns:
        The manifest as written (a copy with the new updated_at).

    Raises:
        ManifestError: The file couldn't be written.
    """
    written = replace(manifest, updated_at=utc_now_iso())
    try:
        write_json_atomic(run_dir / MANIFEST_NAME, written.to_dict())
    except StateFileError as error:
        raise ManifestError(f"can't write the manifest in {run_dir}: {error}") from error
    return written
