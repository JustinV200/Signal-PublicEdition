"""Tests for analysis_chamber.kit: build idempotence, run_env, installs filter, real kit."""

import dataclasses
import os
import subprocess
import sys
from pathlib import Path

import pytest

from analysis_chamber.config import load_config
from analysis_chamber.kit import (
    KIT_TORCH,
    build,
    list_installs,
    make_run_venv,
    run_env,
)
from analysis_chamber.kit import run_venv as run_venv_module
from analysis_chamber.kit.shell import run_cmd


def _config(tmp_path):
    base = load_config(tmp_path / "missing.toml")
    return dataclasses.replace(base, kit_venv=tmp_path / "kit")


def test_build_kit_runs_torch_first_then_skips_when_unchanged(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd):
        calls.append(cmd)
        if cmd[:3] == ["uv", "venv", "--allow-existing"]:
            python = Path(cmd[-1]) / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.touch()
        return "numpy==2.5.5\n" if "freeze" in cmd else ""

    monkeypatch.setattr(build, "run_cmd", fake_run)
    config = _config(tmp_path)
    build.build_kit(config)
    installs = [c for c in calls if "install" in c or "sync" in c]
    assert installs[0][-1] == str(KIT_TORCH) and "sync" in installs[1]
    assert (config.kit_venv / "kit-constraints.txt").read_text() == "numpy==2.5.5\n"
    assert "--index-url" not in (config.kit_venv / "kit-sync.txt").read_text()
    before = len(calls)
    build.build_kit(config)
    assert len(calls) == before


def test_run_env_targets_run_venv(tmp_path):
    config = _config(tmp_path)
    env = run_env(tmp_path / "run", config)
    assert env["VIRTUAL_ENV"] == str(tmp_path / "run" / ".venv")
    run_scripts = str(tmp_path / "run" / ".venv" / "Scripts")
    tool_scripts = str(Path(sys.executable).parent)
    assert env["PATH"].startswith(run_scripts + os.pathsep + tool_scripts)
    assert env["JUPYTER_PATH"] == str(config.kit_venv / "share" / "jupyter")
    constraints = str(config.kit_venv / "kit-constraints.txt")
    assert env["CHAMBER_ENV_FILE"] == str(config.repo_root / ".env")
    assert env["CHAMBER_KIT_CONSTRAINTS"] == env["UV_CONSTRAINT"] == constraints


def test_list_installs_drops_same_version_as_kit(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(cmd):
        if str(config.kit_venv) in cmd[-1]:
            return "requests==2.34.2\nnumpy==2.5.5\n"
        return "requests==2.34.2\nnumpy==2.2.6\ntabulate==0.10.0\nmypkg @ git+https://x/y@abc\n"

    monkeypatch.setattr(run_venv_module, "run_cmd", fake_run)
    assert list_installs(tmp_path / "run", config) == [
        {"package": "numpy", "version": "2.2.6"},
        {"package": "tabulate", "version": "0.10.0"},
        {"package": "mypkg", "version": "git+https://x/y@abc"},
    ]


REAL_KIT = load_config(Path("missing.toml")).kit_venv


@pytest.mark.skipif(not (REAL_KIT / "Scripts" / "python.exe").exists(), reason="kit not built")
def test_real_run_venv_sees_kit_and_lists_only_new_installs(tmp_path):
    config = load_config(tmp_path / "missing.toml")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    venv = make_run_venv(run_dir, config)
    out = subprocess.run(
        [str(venv / "Scripts" / "python.exe"), "-c", "import pandas; print(pandas.__name__)"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "pandas"
    assert list_installs(run_dir, config) == []


def test_run_cmd_drops_uv_constraint_from_env(monkeypatch):
    monkeypatch.setenv("UV_CONSTRAINT", "kit.txt")
    code = "import os; print(os.environ.get('UV_CONSTRAINT'))"
    assert run_cmd([sys.executable, "-c", code]).strip() == "None"
