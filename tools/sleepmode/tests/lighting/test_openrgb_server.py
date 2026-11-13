"""Tests for open_openrgb's skip: no server listening and no OpenRGB.exe means nothing to do."""

from pathlib import Path

import pytest

from sleepmode.lighting import openrgb_server


def _never_start(exe_path: Path) -> None:
    raise AssertionError("started a server with no OpenRGB.exe")


def test_no_server_and_no_exe_is_a_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Never reach the real server (it may be running in the tray).
    monkeypatch.setattr(openrgb_server, "_try_connect", lambda: None)
    monkeypatch.setattr(openrgb_server, "start_server", _never_start)
    assert openrgb_server.open_openrgb(tmp_path / "OpenRGB.exe") is None
    assert openrgb_server.open_openrgb(None) is None
