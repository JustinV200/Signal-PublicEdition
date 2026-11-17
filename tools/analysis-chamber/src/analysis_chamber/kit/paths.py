"""Path helpers for the kit and run venvs (Windows layout)."""

from __future__ import annotations

from pathlib import Path

from analysis_chamber.config import ChamberConfig

REQUIREMENTS_DIR = Path(__file__).parent / "requirements"
KIT_REQUIREMENTS = REQUIREMENTS_DIR / "kit-requirements.txt"  # pinned freeze minus torch
KIT_TORCH = REQUIREMENTS_DIR / "kit-torch.txt"  # torch plus the CUDA index
CONSTRAINTS_NAME = "kit-constraints.txt"
STAMP_NAME = "kit-stamp.txt"


def venv_python(venv: Path) -> Path:
    """The interpreter inside a venv."""
    return venv / "Scripts" / "python.exe"


def constraints_path(config: ChamberConfig) -> Path:
    """Where the kit's constraints file lives."""
    return config.kit_venv / CONSTRAINTS_NAME


def kit_site_packages(config: ChamberConfig) -> Path:
    """The kit's site-packages directory."""
    return config.kit_venv / "Lib" / "site-packages"


def cuda_index_url() -> str:
    """The CUDA torch index from kit-torch.txt's `--index-url` line (the one source of it)."""
    for line in KIT_TORCH.read_text(encoding="utf-8").splitlines():
        if line.startswith("--index-url"):
            return line.split(maxsplit=1)[1].strip()
    raise ValueError(f"no --index-url line in {KIT_TORCH}")
