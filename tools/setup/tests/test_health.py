"""Tool health for the console's Tools page, and the setup window's terminal fallback."""

import subprocess
from pathlib import Path

import pytest

from signal_setup import health, platforms, progress, registry, verify
from signal_setup.cli import ui_launch


@pytest.mark.parametrize(
    ("setup_status", "check", "state"),
    [
        ("", None, health.NOT_SET_UP),
        (progress.SKIPPED, None, health.NOT_SET_UP),
        ("started", None, health.NOT_SET_UP),
        (progress.FAILED, None, health.NOT_SET_UP),
        (progress.DONE, (True, "ok"), health.ACTIVE),
        (progress.DONE, (False, "timed out after 8 s"), health.DOWN),
        (progress.DONE, None, health.DOWN),
    ],
)
def test_classify(setup_status, check, state) -> None:
    assert health.classify(setup_status, check)[0] == state


def test_health_rows_only_check_finished_tools(tmp_path: Path, monkeypatch) -> None:
    data = progress.load(tmp_path)
    progress.set_step(data, "brief", "install", progress.DONE)
    progress.set_skipped(data, "usage")
    progress.save(tmp_path, data)
    checked = []
    monkeypatch.setattr(
        health.verify, "check", lambda root, tool, data, t: checked.append(tool.id) or (False, "x")
    )

    rows = {r["id"]: r["state"] for r in health.health_rows(tmp_path)}

    assert checked == ["brief"]
    assert rows["brief"] == health.DOWN
    assert rows["usage"] == rows["mail"] == health.NOT_SET_UP


@pytest.mark.parametrize("is_tty", [True, False])
def test_ui_falls_back_when_the_window_cant_open(tmp_path: Path, monkeypatch, is_tty) -> None:
    monkeypatch.setattr(platforms, "current", lambda: platforms.LINUX)
    monkeypatch.setattr("sys.stdin.isatty", lambda: is_tty)
    ran = []

    code = ui_launch.launch(tmp_path, terminal_setup=ran.append, opener=lambda *_: 0)

    # A terminal gets the text setup; the skill's shell (no tty) gets exit 1 and nothing runs.
    assert (code, ran) == ((0, [tmp_path]) if is_tty else (1, []))


def test_verify_drops_setups_venv_and_shows_stdout_on_a_pass(tmp_path: Path, monkeypatch) -> None:
    # Regression: setup's VIRTUAL_ENV leaked into a nested `uv run`, whose stderr warning
    # became the Tools page's detail.
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / ".venv"))
    monkeypatch.setattr(verify.shutil, "which", lambda name: rf"C:\bin\{name}.exe")
    seen = {}

    def fake_run(argv, **kwargs):
        seen.update(argv=argv, env=kwargs["env"])
        return subprocess.CompletedProcess(argv, 0, "brief: away off\n", "warning: VIRTUAL_ENV\n")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)
    brief = registry.by_id("brief")

    assert verify.check(tmp_path, brief, progress.load(tmp_path)) == (True, "brief: away off")
    assert seen["argv"][0] == r"C:\bin\uv.exe"
    assert "VIRTUAL_ENV" not in seen["env"]
