"""Tests for kit.install_into_run_venv with a fake uv (resolve output, install call, shadow)."""

import dataclasses
from pathlib import Path

import pytest

from analysis_chamber.config import load_config
from analysis_chamber.kit import KitError, install, install_into_run_venv

KIT_PINS = "numpy==2.5.5\ntorch==2.15.0+cu132\n"


def _setup(tmp_path, monkeypatch, compile_out, constraints=KIT_PINS):
    config = dataclasses.replace(load_config(tmp_path / "missing.toml"), kit_venv=tmp_path / "kit")
    config.kit_venv.mkdir(exist_ok=True)
    kit_file = config.kit_venv / "kit-constraints.txt"
    if constraints is not None:
        kit_file.write_text(constraints)
    calls = []  # (cmd, text of its constraints file (compile) or -r file (install))

    def fake_run(cmd):
        constrained = (
            Path(cmd[cmd.index("--constraint") + 1]).read_text() if "compile" in cmd else ""
        )
        calls.append((cmd, constrained))
        if "compile" in cmd:
            if isinstance(compile_out, Exception):
                raise compile_out
            return compile_out
        calls[-1] = (cmd, Path(cmd[cmd.index("-r") + 1]).read_text())
        return ""

    monkeypatch.setattr(install, "run_cmd", fake_run)
    return config, calls


def test_installs_only_what_the_kit_lacks_with_no_deps(tmp_path, monkeypatch):
    out = "accelerate==1.2.0\nnumpy==2.5.5\nmypkg @ https://x/y.whl\ntorch==2.15.0+cu132\n"
    config, calls = _setup(tmp_path, monkeypatch, out)
    got = install_into_run_venv(tmp_path / "run", config, ["accelerate"])
    assert got == [
        {"package": "accelerate", "version": "1.2.0"},
        {"package": "mypkg", "version": "https://x/y.whl"},
    ]
    for cmd, _ in calls:
        assert "unsafe-best-match" in cmd and "--extra-index-url" in cmd
    install_cmd, lock_text = calls[-1]
    assert "--no-deps" in install_cmd
    assert lock_text == "accelerate==1.2.0\nmypkg @ https://x/y.whl\n"


def test_nothing_to_install_when_kit_already_has_it(tmp_path, monkeypatch):
    config, calls = _setup(tmp_path, monkeypatch, "numpy==2.5.5\n")
    assert install_into_run_venv(tmp_path / "run", config, ["numpy"]) == []
    assert len(calls) == 1  # only the resolve ran


def test_shadow_refused_without_flag_and_allowed_but_never_for_torch(tmp_path, monkeypatch):
    config, _ = _setup(tmp_path, monkeypatch, KitError("conflict"))
    with pytest.raises(KitError, match="--allow-shadow"):
        install_into_run_venv(tmp_path / "run", config, ["numpy==2.2.6"])
    config, calls = _setup(tmp_path, monkeypatch, "numpy==2.2.6\n")
    got = install_into_run_venv(tmp_path / "run", config, ["numpy==2.2.6", "torch"], True)
    assert got == [{"package": "numpy", "version": "2.2.6"}]
    constrained = calls[0][1]
    assert "numpy" not in constrained and "torch==2.15.0+cu132" in constrained


def test_missing_kit_constraints_says_kit_not_built(tmp_path, monkeypatch):
    config, _ = _setup(tmp_path, monkeypatch, "", constraints=None)
    with pytest.raises(KitError, match="kit not built"):
        install_into_run_venv(tmp_path / "run", config, ["numpy"])
