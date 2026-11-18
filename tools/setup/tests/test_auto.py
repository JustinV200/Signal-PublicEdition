"""`setup auto`: the picks' automatic steps in order, each tool stopping where it needs you."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from signal_setup import platforms, progress
from signal_setup.cli import main
from signal_setup.steps import run


def _fake_commands(tmp_path: Path, monkeypatch, failing: str = "") -> list[str]:
    """Record each command's `--project tools/<x>` (or its first word); `failing`'s exit 1."""
    started: list[str] = []

    def fake_run(argv, cwd):
        name = argv[argv.index("--project") + 1] if "--project" in argv else argv[0]
        started.append(name)
        return SimpleNamespace(returncode=1 if name == failing else 0)

    def refuse(*_args, **_kwargs):
        raise AssertionError("setup auto must never prompt")

    monkeypatch.setattr(main, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(platforms, "current", lambda: platforms.WINDOWS)  # the tools' OS
    monkeypatch.setattr(run.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(run.subprocess, "run", fake_run)
    monkeypatch.setattr("builtins.input", refuse)
    monkeypatch.setattr(run, "missing", lambda names: [])  # every program is "installed"
    return started


def _pick(tmp_path: Path, chosen: list[str]) -> None:
    """Picks `chosen`; mail's address is known, so its sign-in is next after install."""
    data = progress.load(tmp_path)
    data["chosen"] = chosen
    for step in ("google-project", "email"):
        progress.set_step(data, "mail", step, progress.DONE)
    data["answers"]["email"] = "owner@example.com"
    progress.save(tmp_path, data)


def _result(capsys) -> dict:
    """The JSON object `setup auto` ends with."""
    out = capsys.readouterr().out
    return json.loads(out[out.rindex("\n{") :])


def test_auto_runs_picks_in_order_and_stops_each_where_it_needs_you(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    started = _fake_commands(tmp_path, monkeypatch)
    _pick(tmp_path, ["mail", "browser", "brief"])  # vault, calendar etc. aren't picked

    assert main.main(["auto"]) == 3

    # Registry order, installs only: no optional step (browser's docker), no browser
    # sign-in (mail's signin), nothing of a tool that wasn't picked.
    assert started == ["tools/brief", "tools/browser", "tools/mail"]
    stopped = [(s["tool"], s["step"], s["reason"]) for s in _result(capsys)["stopped"]]
    assert stopped == [("browser", "config", "needs_you"), ("mail", "signin", "needs_you")]
    data = progress.load(tmp_path)
    assert progress.step_status(data, "brief", "install") == progress.DONE
    assert progress.step_status(data, "browser", "docker") == ""  # still waits for its click
    assert sorted(p.name for p in tmp_path.iterdir()) == [".setup"]  # no Claude Code config

    # Run again: done steps aren't repeated; one tool on its own runs only that tool.
    started.clear()
    assert main.main(["auto", "brief"]) == 0
    assert started == []


def test_auto_failure_ends_that_tool_only(tmp_path: Path, monkeypatch, capsys) -> None:
    started = _fake_commands(tmp_path, monkeypatch, failing="tools/brief")
    _pick(tmp_path, ["brief", "usage"])

    assert main.main(["auto"]) == 1

    assert started == ["tools/brief", "tools/usage"]
    assert [s["reason"] for s in _result(capsys)["stopped"]] == ["failed"]
    assert progress.step_status(progress.load(tmp_path), "brief", "install") == progress.FAILED


@pytest.mark.parametrize("tool_ids", [["vault"], ["nope"]])
def test_auto_runs_nothing_unpicked_or_unknown(tmp_path: Path, monkeypatch, tool_ids) -> None:
    started = _fake_commands(tmp_path, monkeypatch)
    _pick(tmp_path, ["brief"])

    code = main.main(["auto", *tool_ids])

    assert started == []
    assert code == 2  # unknown, or nothing named can run: never "done"
