"""The setup window's terminal fallback."""

from pathlib import Path

import pytest

from signal_setup import platforms
from signal_setup.cli import ui_launch


@pytest.mark.parametrize("is_tty", [True, False])
def test_ui_falls_back_when_the_window_cant_open(tmp_path: Path, monkeypatch, is_tty) -> None:
    monkeypatch.setattr(platforms, "current", lambda: platforms.LINUX)
    monkeypatch.setattr("sys.stdin.isatty", lambda: is_tty)
    ran = []

    code = ui_launch.launch(
        tmp_path, "mail", terminal_setup=lambda *args: ran.append(args), opener=lambda *_: 0
    )

    # A terminal gets the text setup for that tool; the skill's shell (no tty) gets exit 1.
    assert (code, ran) == ((0, [(tmp_path, "mail")]) if is_tty else (1, []))
