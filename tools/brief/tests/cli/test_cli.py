"""Tests for the `brief` command line."""

import pytest
from signal_brief import BRIEF_TAG
from support import at, log, make_paths

from brief_tool import cli


def test_show_plain_piped_prints_no_frame(tmp_path, monkeypatch, capsys) -> None:
    paths = make_paths(tmp_path)
    log(paths, "new", "Lab grades posted", at(20, 9))
    monkeypatch.setattr(cli, "BriefPaths", lambda: paths)

    with pytest.raises(SystemExit) as exited:
        cli.main(["show", "--plain"])  # capsys's stdout isn't a TTY, like a pipe

    out = capsys.readouterr().out
    assert exited.value.code == 0
    assert "Lab grades posted" in out and BRIEF_TAG not in out
