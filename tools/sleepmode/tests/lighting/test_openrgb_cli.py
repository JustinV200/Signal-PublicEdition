"""Tests for OpenRGB.exe's command line through cmd.exe (a stand-in batch file, not OpenRGB)."""

from pathlib import Path

import pytest

from sleepmode.lighting import openrgb_cli

# Writes its arguments next to itself, so the test sees what cmd.exe really ran.
ECHO_ARGS_BAT = '@echo %*> "%~dp0args.txt"\r\n'


def test_a_path_with_an_ampersand_runs_and_one_with_a_percent_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "R&D"  # unquoted, cmd.exe would split the line at the &
    folder.mkdir()
    exe_path = folder / "OpenRGB.bat"
    exe_path.write_text(ECHO_ARGS_BAT, encoding="ascii")

    openrgb_cli._run_cli(exe_path, ("-sp", "sleepmode-before"))

    assert (folder / "args.txt").read_text(encoding="ascii").strip() == "-sp sleepmode-before"
    # cmd.exe expands %NAME% even inside quotes, so such a path can't be run safely.
    with pytest.raises(OSError, match="%"):
        openrgb_cli._command_line(Path(r"C:\100%\OpenRGB.exe"), ())
