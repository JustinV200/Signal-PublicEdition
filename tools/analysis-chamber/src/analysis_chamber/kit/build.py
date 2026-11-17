"""Build (or skip) the shared analysis kit venv with CUDA torch."""

from __future__ import annotations

import hashlib

from analysis_chamber.config import ChamberConfig
from analysis_chamber.kit.paths import (
    KIT_REQUIREMENTS,
    KIT_TORCH,
    STAMP_NAME,
    constraints_path,
    venv_python,
)
from analysis_chamber.kit.shell import run_cmd

PYTHON_VERSION = "3.12"
SYNC_NAME = "kit-sync.txt"


def _sync_requirements() -> str:
    """kit-torch.txt's pin (minus its index option) plus every other kit pin."""
    torch_pins = [
        line
        for line in KIT_TORCH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("--")
    ]
    return "\n".join(torch_pins) + "\n" + KIT_REQUIREMENTS.read_text(encoding="utf-8")


def _requirements_digest() -> str:
    """Hash of the pinned requirement files; changes when the pins change."""
    digest = hashlib.sha256()
    for path in (KIT_TORCH, KIT_REQUIREMENTS):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def build_kit(config: ChamberConfig) -> None:
    """Build or update config.kit_venv; a no-op when it already matches the pins.

    Torch goes in first from its CUDA index alone (never --extra-index-url, see the
    spike), then the rest from PyPI via uv pip sync. Finally writes kit-constraints.txt, a freeze
    used to constrain installs in run venvs. Raises KitError if a uv command fails.
    """
    kit = config.kit_venv
    python = venv_python(kit)
    stamp = kit / STAMP_NAME
    digest = _requirements_digest()
    if python.exists() and stamp.exists() and stamp.read_text().strip() == digest:
        return
    run_cmd(["uv", "venv", "--allow-existing", "--python", PYTHON_VERSION, str(kit)])
    run_cmd(["uv", "pip", "install", "--python", str(python), "-r", str(KIT_TORCH)])
    # sync (not install) so pins dropped from the files are uninstalled. The sync file also
    # lists torch, which is already installed from the CUDA index, so sync keeps it as is.
    sync_file = kit / SYNC_NAME
    sync_file.write_text(_sync_requirements(), encoding="utf-8")
    run_cmd(["uv", "pip", "sync", "--python", str(python), str(sync_file)])
    freeze = run_cmd(["uv", "pip", "freeze", "--python", str(python)])
    constraints_path(config).write_text(freeze, encoding="utf-8")
    stamp.write_text(digest, encoding="utf-8")  # last, so a failed build retries
