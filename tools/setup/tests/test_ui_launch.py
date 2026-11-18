"""The setup window: its terminal fallback, and the console port that `--port` stores."""

import subprocess
from pathlib import Path

import pytest

from signal_setup import platforms, progress
from signal_setup.cli import main as setup_main
from signal_setup.cli import ui_launch


@pytest.mark.parametrize("is_tty", [True, False])
def test_ui_falls_back_when_the_window_cant_open(tmp_path: Path, monkeypatch, is_tty) -> None:
    monkeypatch.setattr(platforms, "current", lambda: platforms.LINUX)
    monkeypatch.setattr("sys.stdin.isatty", lambda: is_tty)
    ran = []

    code = ui_launch.launch(tmp_path, "mail", terminal_setup=lambda *args: ran.append(args))

    # A terminal gets the text setup for that tool; the skill's shell (no tty) gets exit 1.
    assert (code, ran) == ((0, [(tmp_path, "mail")]) if is_tty else (1, []))


def test_a_failed_open_names_who_holds_the_port(tmp_path: Path, monkeypatch, capsys) -> None:
    # Nothing is opened or looked up for real: console open "fails", the holder is a fake.
    monkeypatch.setattr(ui_launch, "_bootstrap", lambda root: "")
    monkeypatch.setattr(subprocess, "run", lambda argv, cwd: subprocess.CompletedProcess(argv, 1))
    holder = r"another checkout's console, D:\Other\Signal"
    monkeypatch.setattr(ui_launch, "port_holder_words", lambda port, root: holder)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    assert ui_launch.launch(tmp_path, port=8791) == 1

    out = capsys.readouterr().out
    assert f"port 8791 is used by {holder}" in out
    assert "--port <a free port>" in out


@pytest.mark.parametrize(
    ("window", "stored", "port"),
    [
        (["--port", "8791"], None, "8791"),
        (["ui", "--port", "8791"], None, "8791"),
        # a hand-edited bad answer: the window and the logon step both fall back to 8790
        ([], "80", "8790"),
    ],
)
def test_port_opens_the_window_and_fills_the_logon_step(
    tmp_path, monkeypatch, window, stored, port
) -> None:
    # Temp progress only; nothing is installed, opened or registered: every command is recorded.
    monkeypatch.setattr(setup_main, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ui_launch, "_bootstrap", lambda root: "")
    monkeypatch.setattr("shutil.which", lambda name: name)
    if stored is not None:
        progress.save(tmp_path, {"chosen": [], "answers": {"port": stored}, "tools": {}})
    commands = []

    def record(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
        commands.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(subprocess, "run", record)

    assert setup_main.main(window) == 0
    if "--port" in window:
        with pytest.raises(SystemExit):  # outside register.ps1's range: refused, never stored
            setup_main.main([*window[:-1], "80"])
    assert setup_main.main([]) == 0  # a later bare `setup` keeps the stored port
    assert setup_main.main(["apply", "console", "logon"]) == 0

    *opened, registered = commands
    assert [argv[argv.index("--port") + 1] for argv in opened] == [port, port]
    assert registered[-2:] == ["-Port", port]
