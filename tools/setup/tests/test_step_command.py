"""`setup step <tool> <step>`: runs that one step, asks nothing else, and wires nothing."""

from pathlib import Path
from types import SimpleNamespace

from signal_setup import progress
from signal_setup.cli import main
from signal_setup.steps import run
from signal_setup.ui import flow


def test_step_runs_one_step_and_does_no_wiring(tmp_path: Path, monkeypatch) -> None:
    started = []
    monkeypatch.setattr(main, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(
        run.subprocess,
        "run",
        lambda argv, cwd: started.append(argv) or SimpleNamespace(returncode=0),
    )

    def refuse(*_args, **_kwargs):
        raise AssertionError("setup step must not prompt or wire")

    # A run step asks nothing (no "Install?" replay), and nothing reaches the wiring.
    monkeypatch.setattr("builtins.input", refuse)
    monkeypatch.setattr(flow.wiring, "apply_plan", refuse)

    assert main.main(["step", "vault", "init"]) == 0

    assert [argv[-2:] for argv in started] == [["vault", "init"]]  # only that step ran
    data = progress.load(tmp_path)
    assert progress.step_status(data, "vault", "init") == progress.DONE
    assert progress.step_status(data, "vault", "install") == ""
    assert sorted(p.name for p in tmp_path.iterdir()) == [".setup"]  # no .mcp.json, no .claude
    # The registry is the check on ids: an unknown step runs nothing (exit 2).
    assert main.main(["step", "vault", "nope"]) == 2
    assert len(started) == 1


def test_step_keeps_what_the_window_saved_while_it_ran(tmp_path: Path, monkeypatch) -> None:
    # Regression: the step saved its early snapshot, undoing the window's writes meanwhile.
    def window_writes_meanwhile(argv, cwd):
        data = progress.load(tmp_path)
        progress.set_step(data, "mail", "signin", progress.DONE)
        data["chosen"] = ["mail"]
        progress.save(tmp_path, data)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(main, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(run.subprocess, "run", window_writes_meanwhile)

    assert main.main(["step", "vault", "init"]) == 0

    data = progress.load(tmp_path)
    assert progress.step_status(data, "mail", "signin") == progress.DONE
    assert data["chosen"] == ["mail"]
    assert progress.step_status(data, "vault", "init") == progress.DONE
