"""`console serve` writes its own .state/server.log, so a logon-task server isn't silent."""

import logging
import socket
from pathlib import Path

from signal_console.cli import commands, main


def _drop_file_handlers(folder: Path) -> None:
    # serve's handler keeps the log open; Windows can't delete the temp folder until it closes.
    root = logging.getLogger()
    for handler in list(root.handlers):
        if Path(getattr(handler, "baseFilename", "/")).parent == folder:
            root.removeHandler(handler)
            handler.close()


def test_a_taken_port_lands_in_server_log(tmp_path, monkeypatch) -> None:
    # Temp state only, and a port this test holds itself (never the everyday 8790).
    monkeypatch.setattr(commands, "STATE_DIR", tmp_path)
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        try:
            code = main(["serve", "--port", str(port)])
        finally:
            _drop_file_handlers(tmp_path)

    assert code == 1
    # The reason (asyncio's bind error) is in the file, not only on a stderr pythonw lacks.
    assert "bind" in (tmp_path / "server.log").read_text("utf-8")
