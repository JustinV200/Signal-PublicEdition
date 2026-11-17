"""Install packages into a run venv without duplicating or silently replacing kit packages."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from analysis_chamber.config import ChamberConfig
from analysis_chamber.kit.freeze import parse_freeze
from analysis_chamber.kit.paths import constraints_path, cuda_index_url, venv_python
from analysis_chamber.kit.shell import KitError, run_cmd

SHADOW_HINT = " (to replace a kit package, list it in the request and pass --allow-shadow)"
NEVER_SHADOW = {"torch"}  # the CUDA build must stay exactly pinned
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


# Needed with the extra index: first-index would take a package only from the cu132 index when
# it has it, and that index lacks most kit versions. Safe here because every kit package is
# exactly pinned by the constraints, so only names the kit lacks are exposed to best-match.
def _index_flags() -> list[str]:
    """uv flags that add the CUDA index (read from kit-torch.txt) with best-match resolution."""
    return ["--extra-index-url", cuda_index_url(), "--index-strategy", "unsafe-best-match"]


def _normalise(name: str) -> str:
    """Lowercase package name with runs of `-_.` as one dash."""
    return re.sub(r"[-_.]+", "-", name.lower())


def _requested_names(packages: list[str]) -> set[str]:
    """Normalised package names from requirement strings like 'numpy==2.2.6'."""
    names = (_NAME.match(spec.strip()) for spec in packages)
    return {_normalise(m.group()) for m in names if m}


def _constraints_text(constraints_file: Path, relaxed: set[str]) -> str:
    """The kit constraints minus the packages the caller may shadow (never torch)."""
    lines = constraints_file.read_text(encoding="utf-8").splitlines()
    dropped = relaxed - NEVER_SHADOW
    kept = [x for x in lines if _normalise(x.split("==")[0]) not in dropped]
    return "\n".join(kept) + "\n"


def _pin_line(name: str, version: str) -> str:
    """A requirement line: `name==version`, or `name @ url` when the version is a url."""
    return f"{name} @ {version}\n" if "://" in version else f"{name}=={version}\n"


def install_into_run_venv(
    run_dir: Path, config: ChamberConfig, packages: list[str], allow_shadow: bool = False
) -> list[dict]:
    """Install packages (and their new dependencies) into run_dir/.venv, returning what landed.

    Resolves the whole requirement set with `uv pip compile` against the kit constraints
    (the cu132 index is added so torch-dependent packages resolve), then installs with
    --no-deps only what is not already in the kit at the same version. A package that would
    replace a kit package with another version is refused unless allow_shadow is True; torch
    is never shadowed. Raises KitError if the kit is not built or a resolve/install fails.
    """
    kit_file = constraints_path(config)
    if not kit_file.exists():
        raise KitError("kit not built; run analysis-chamber kit build")
    relaxed = _requested_names(packages) if allow_shadow else set()
    python = str(venv_python(run_dir / ".venv"))
    with tempfile.TemporaryDirectory() as tmp:
        requirements = Path(tmp) / "requested.in"
        constraints = Path(tmp) / "constraints.txt"
        requirements.write_text("\n".join(packages) + "\n", encoding="utf-8")
        constraints.write_text(_constraints_text(kit_file, relaxed), encoding="utf-8")
        compile_cmd = ["uv", "pip", "compile", str(requirements), "--python", python]
        compile_cmd += ["--constraint", str(constraints), "--no-header", "--no-annotate"]
        try:
            resolved = parse_freeze(run_cmd([*compile_cmd, *_index_flags()]))
        except KitError as exc:
            hint = "" if allow_shadow else SHADOW_HINT
            raise KitError(f"cannot resolve {packages}{hint}: {exc}") from exc
        kit = parse_freeze(kit_file.read_text(encoding="utf-8"))
        todo = {n: v for n, v in resolved.items() if kit.get(n) != v}
        if not todo:
            return []
        lock = Path(tmp) / "install.txt"
        lock.write_text("".join(_pin_line(n, v) for n, v in todo.items()), encoding="utf-8")
        install_cmd = ["uv", "pip", "install", "--python", python, "--no-deps", "-r", str(lock)]
        run_cmd([*install_cmd, *_index_flags()])
    return [{"package": n, "version": v} for n, v in todo.items()]
