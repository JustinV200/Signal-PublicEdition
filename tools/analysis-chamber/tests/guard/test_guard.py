"""Security table for analysis_chamber.guard: run locations and the publish block."""

from dataclasses import replace
from pathlib import Path

import pytest

from analysis_chamber.config import load_config
from analysis_chamber.guard import LeakError, can_publish, check_run_location
from analysis_chamber.runs import REPORT_FORMATS, Manifest


@pytest.fixture
def config(tmp_path: Path):
    repo = tmp_path / "Signal"
    return replace(
        load_config(tmp_path / "missing.toml"),
        repo_root=repo,
        analyses_root=repo / "life" / "analyses",
        private_root=tmp_path / "chamber-private",
    )


# (personal flag, run folder relative to tmp_path, allowed?)
LOCATION_TABLE = [
    (None, "chamber-private/r", True),
    (True, "chamber-private/r", True),
    (False, "Signal/life/analyses/r", True),
    (None, "Signal/life/analyses/r", False),
    (True, "Signal/life/analyses/r", False),
    (True, "Signal/tools/x/r", False),
    (False, "SIGNAL/LIFE/ANALYSES/r", True),  # passes only if case is ignored (Windows)
    (True, "chamber-private/../Signal/r", False),  # `..` resolved
    (True, "elsewhere/r", False),  # outside the repo but not in private_root
    (None, "elsewhere/r", False),
    (False, "chamber-private/r", False),
    (False, "Signal/life/r", False),
    (False, "Signal/life/analyses-evil/r", False),  # prefix isn't containment
]


@pytest.mark.parametrize(("personal", "relative", "allowed"), LOCATION_TABLE)
def test_run_location(config, tmp_path: Path, personal, relative: str, allowed: bool) -> None:
    manifest = Manifest(id="r", question="q", personal=personal)
    if allowed:
        check_run_location(manifest, tmp_path / relative, config)
    else:
        with pytest.raises(LeakError):
            check_run_location(manifest, tmp_path / relative, config)


def test_root_with_dotdot_is_resolved(config, tmp_path: Path) -> None:
    # A misconfigured private_root inside the repo must not let personal runs in,
    # and repo_root written with `..` must still contain runs under the real folder.
    # private_root sits inside the real repo, so only the repo_root check can refuse it.
    dotted = replace(
        config,
        repo_root=tmp_path / "x" / ".." / "Signal",
        private_root=tmp_path / "Signal" / "private",
    )
    manifest = Manifest(id="r", question="q", personal=True)
    with pytest.raises(LeakError):
        check_run_location(manifest, tmp_path / "Signal" / "private" / "r", dotted)


@pytest.mark.parametrize(
    ("personal", "report_format", "allowed"),
    [
        (False, "artifact", True),
        (True, "artifact", False),
        (None, "artifact", False),
        (False, None, False),
        *[(False, fmt, False) for fmt in sorted(REPORT_FORMATS - {"artifact"})],
    ],
)
def test_can_publish(personal, report_format, allowed: bool) -> None:
    manifest = Manifest(id="r", question="q", personal=personal, report_format=report_format)
    assert can_publish(manifest) is allowed
