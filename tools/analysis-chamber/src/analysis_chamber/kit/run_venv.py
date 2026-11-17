"""Per-run venvs layered on the kit, their env overrides and their extra installs."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.kit.freeze import parse_freeze
from analysis_chamber.kit.paths import constraints_path, kit_site_packages, venv_python
from analysis_chamber.kit.shell import run_cmd

KIT_PTH_NAME = "_kit.pth"


def make_run_venv(run_dir: Path, config: ChamberConfig) -> Path:
    """Create run_dir/.venv layered on the kit and return its path.

    Uses a .pth with site.addsitedir (--system-site-packages would see the base
    Python, not the kit). Run installs shadow kit versions. Raises KitError.
    """
    venv = run_dir / ".venv"
    kit_python = str(venv_python(config.kit_venv))
    run_cmd(["uv", "venv", "--allow-existing", "--python", kit_python, str(venv)])
    pth = venv / "Lib" / "site-packages" / KIT_PTH_NAME
    pth.write_text(f'import site; site.addsitedir(r"{kit_site_packages(config)}")\n')
    return venv


def run_env(run_dir: Path, config: ChamberConfig) -> dict[str, str]:
    """Env overrides so plain python / uv pip in a run target the run venv.

    Installs should go through `analysis-chamber install` (install_into_run_venv). As a guard
    for a plain `uv pip install`, UV_CONSTRAINT points at the kit constraints so it cannot pull
    a CPU torch; CHAMBER_KIT_CONSTRAINTS is the same file for reference.
    JUPYTER_PATH is needed because nbconvert looks for data files under sys.prefix.
    """
    venv = run_dir / ".venv"
    return {
        "VIRTUAL_ENV": str(venv),
        # Tool venv Scripts (where analysis-chamber.exe lives) so the lead can call
        # `analysis-chamber gpu` and `analysis-chamber install`.
        "PATH": os.pathsep.join(
            [str(venv / "Scripts"), str(Path(sys.executable).parent), os.environ.get("PATH", "")]
        ),
        "JUPYTER_PATH": str(config.kit_venv / "share" / "jupyter"),
        "CHAMBER_KIT_CONSTRAINTS": str(constraints_path(config)),
        "UV_CONSTRAINT": str(constraints_path(config)),
        # Where chamber_get_api_key appends API keys, for the lead's code to read.
        "CHAMBER_ENV_FILE": str(config.repo_root / ".env"),
    }


def list_installs(run_dir: Path, config: ChamberConfig) -> list[dict]:
    """{package, version} for packages in the run venv that the kit does not already have.

    Same name and version in the kit is a duplicate install of a dependency, not an
    addition, so it is dropped (a different version is a real shadow and stays). URL
    installs always count: a url is never a kit version.
    """
    run_python = venv_python(run_dir / ".venv")
    run_pins = parse_freeze(run_cmd(["uv", "pip", "freeze", "--python", str(run_python)]))
    kit_python = venv_python(config.kit_venv)
    kit_pins = parse_freeze(run_cmd(["uv", "pip", "freeze", "--python", str(kit_python)]))
    return [
        {"package": name, "version": version}
        for name, version in run_pins.items()
        if kit_pins.get(name) != version
    ]
