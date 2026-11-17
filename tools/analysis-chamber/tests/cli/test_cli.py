"""CLI parsing and dispatch to the daemon client, with a fake analysis_chamber.daemon."""

import sys
import types

import pytest

from analysis_chamber.cli import main


class FakeError(Exception):
    """Stands in for DaemonError."""


class FakeClient:
    calls: list[tuple] = []

    def __init__(self, state_dir):
        pass

    def start(self, question):
        self.calls.append(("start", question))
        return {"run_id": "r1"}

    def approve(self, run_id, edits=None, personal=None):
        self.calls.append(("approve", run_id, edits, personal))
        return {"ok": True}

    def status(self, run_id):
        raise FakeError("no such run")

    def list(self):
        self.calls.append(("list",))
        return []

    def ask(self, run_id, question):
        self.calls.append(("ask", run_id, question))
        return {"answer": "x"}

    def cancel(self, run_id):
        self.calls.append(("cancel", run_id))
        return {}


@pytest.fixture(autouse=True)
def fake_daemon(monkeypatch):
    FakeClient.calls = []
    module = types.SimpleNamespace(DaemonClient=FakeClient, DaemonError=FakeError)
    monkeypatch.setitem(sys.modules, "analysis_chamber.daemon", module)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["start", "why?"], ("start", "why?")),
        (["approve", "r1", "--personal", "yes"], ("approve", "r1", None, True)),
        (["approve", "r1", "--personal", "no", "--edits", "m"], ("approve", "r1", "m", False)),
        (["approve", "r1"], ("approve", "r1", None, None)),
        (["list"], ("list",)),
        (["ask", "r1", "q"], ("ask", "r1", "q")),
        (["cancel", "r1"], ("cancel", "r1")),
    ],
)
def test_subcommand_calls_client(argv, expected):
    assert main(argv) == 0
    assert FakeClient.calls == [expected]


def test_daemon_error_exits_nonzero(capsys):
    assert main(["status", "r1"]) == 1
    assert "no such run" in capsys.readouterr().err


def test_gpu_strips_separator_and_returns_exit_code(monkeypatch):
    seen = {}

    def run_locked(state_dir, cmd):
        seen["cmd"] = cmd
        return 7

    monkeypatch.setitem(
        sys.modules, "analysis_chamber.gpu", types.SimpleNamespace(run_locked=run_locked)
    )
    assert main(["gpu", "--", "python", "x.py"]) == 7
    assert seen["cmd"] == ["python", "x.py"]


def test_install_needs_manifest_and_passes_flags(monkeypatch, tmp_path, capsys):
    seen = {}

    def install_into_run_venv(run_dir, config, packages, allow_shadow=False):
        seen["args"] = (run_dir, packages, allow_shadow)
        return [{"package": "foo", "version": "1"}]

    class KitError(Exception):
        pass

    monkeypatch.setitem(
        sys.modules,
        "analysis_chamber.kit",
        types.SimpleNamespace(install_into_run_venv=install_into_run_venv, KitError=KitError),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["install", "foo"]) == 1  # no manifest.json here
    (tmp_path / "manifest.json").write_text("{}")
    assert main(["install", "--allow-shadow", "foo", "bar"]) == 0
    assert seen["args"] == (tmp_path, ["foo", "bar"], True)


@pytest.mark.parametrize("argv", [["kit", "build"], ["install", "foo"]])
def test_kit_failures_exit_one_with_one_line(argv, monkeypatch, tmp_path, capsys):
    def boom(*args, **kwargs):
        raise OSError("cannot run uv")

    kit = types.SimpleNamespace(build_kit=boom, install_into_run_venv=boom, KitError=ValueError)
    monkeypatch.setitem(sys.modules, "analysis_chamber.kit", kit)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "manifest.json").write_text("{}")
    assert main(argv) == 1
    assert capsys.readouterr().err.strip().count("\n") == 0
