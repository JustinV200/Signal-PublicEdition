"""run_daemon's startup order: the port is claimed before the token or the camera are touched."""

import socket

import pytest

from whiteboard.config import DisplaySettings, Settings
from whiteboard.daemon import serve

pytestmark = pytest.mark.asyncio


async def test_a_second_daemon_dies_on_the_port_before_touching_token_or_camera(
    tmp_path, monkeypatch
) -> None:
    # Regression: the token was written before binding, so a second `serve`
    # overwrote it, then died on the port, and the survivor 403'd every client.
    opened_cameras = []

    class FakeCamera:
        def __init__(self, settings) -> None:
            pass

        def open(self) -> None:
            opened_cameras.append(True)

        def close(self) -> None:
            pass

    monkeypatch.setattr(serve, "Camera", FakeCamera)
    (tmp_path / "token").write_text("running-daemon-token", encoding="utf-8")
    with socket.socket() as running_daemon:
        running_daemon.bind(("127.0.0.1", 0))
        running_daemon.listen()
        port = running_daemon.getsockname()[1]
        settings = Settings(display=DisplaySettings(port=port, launch_kiosk=False))
        with pytest.raises(OSError):
            await serve.run_daemon(settings, tmp_path)
    assert (tmp_path / "token").read_text(encoding="utf-8") == "running-daemon-token"
    assert opened_cameras == []
