"""Tests for analysis_chamber.config: example parity, overrides and boundary checks."""

import tomllib
from pathlib import Path

import pytest

from analysis_chamber.config import KNOWN_KEYS, REPO_ROOT, TOOL_DIR, ConfigError, load_config


def test_example_matches_code_defaults(tmp_path: Path) -> None:
    example = TOOL_DIR / "config.example.toml"
    with example.open("rb") as handle:
        assert set(tomllib.load(handle)) == KNOWN_KEYS  # no key missing from the example
    defaults = load_config(tmp_path / "missing.toml")
    assert load_config(example) == defaults


def test_toml_overrides_and_relative_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('max_parallel_runs = 5\nprivate_root = "elsewhere/private"\n', encoding="utf-8")
    config = load_config(path)
    assert config.max_parallel_runs == 5
    assert config.private_root == REPO_ROOT / "elsewhere" / "private"
    assert config.lead_model == "claude-opus-5-5"


@pytest.mark.parametrize(
    "text",
    [
        "max_parallel_runs = 0",
        "max_parallel_runs = true",
        'lead_model = ""',
        "bogus = 1",
        "x =",
        r"kit_venv = '%NO_SUCH_VAR_XYZ%\kit'",  # unset var would land in the repo
        r"log_dir = '$NO_SUCH_VAR_XYZ\logs'",
        r"log_dir = '${NO_SUCH_VAR_XYZ}\logs'",
    ],
)
def test_bad_config_is_refused(tmp_path: Path, text: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
