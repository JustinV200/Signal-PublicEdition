"""`console open` says what's wrong at once: no built page, a taken port, a server that exits.

Temp state only (tmp_health_paths), and no real server or Edge is ever started:
spawn_detached is a fake that records the command.
"""

from pathlib import Path
from typing import BinaryIO

import pytest
from conftest import tmp_health_paths

from signal_console.cli import open_command, server_start
from signal_console.cli.server_start import OpenError
from signal_console.health import SETUP_COMMAND, server_check
from signal_console.health.port_holder import PortHolder

OTHER_CHECKOUT = Path(r"D:\Other\Signal")
BIND_ERROR = "OSError: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 1)"


class ExitedServer:
    """Stands in for the server's Popen: it has already exited with code 1."""

    returncode = 1

    def poll(self) -> int:
        return self.returncode


@pytest.fixture
def started(monkeypatch) -> list[list[str]]:
    """The commands spawn_detached was asked to start; each 'server' logs a bind error and exits."""
    commands: list[list[str]] = []

    def fake_spawn(command: list[str], cwd: Path, log_file: BinaryIO, env) -> ExitedServer:
        commands.append(command)
        log_file.write(f"Traceback (most recent call last):\n{BIND_ERROR}\n".encode())
        return ExitedServer()

    monkeypatch.setattr(server_start, "spawn_detached", fake_spawn)
    monkeypatch.setattr(open_command, "spawn_detached", fake_spawn)
    monkeypatch.setattr(server_start, "POLL_INTERVAL_S", 0)
    return commands


@pytest.mark.parametrize(
    ("built", "holder", "named"),
    [
        # no web/dist: the one command to run, and nothing built or started
        (False, None, SETUP_COMMAND),
        # another checkout's console on the port: that checkout and both ways out
        (
            True,
            PortHolder(4242, "python.exe", OTHER_CHECKOUT / "tools" / "console"),
            "--port <a free port>",
        ),
    ],
)
def test_open_stops_before_starting_anything(
    tmp_path, monkeypatch, started, built, holder, named
) -> None:
    paths = tmp_health_paths(tmp_path)
    if built:
        paths.web_dist_dir.mkdir()
        (paths.web_dist_dir / "index.html").write_text("<!doctype html>")
    monkeypatch.setattr(server_check, "find_port_holder", lambda port: holder)

    with pytest.raises(OpenError) as error:
        open_command.open_console(paths)

    assert named in str(error.value)
    if holder is not None:
        assert f"another checkout, {OTHER_CHECKOUT}" in str(error.value)
        assert "Stop that program" in str(error.value)
    assert started == []


def test_a_server_that_exits_during_the_wait_is_reported_with_its_log_line(
    tmp_path, started, capsys
) -> None:
    paths = tmp_health_paths(tmp_path)
    paths.web_dist_dir.mkdir()
    (paths.web_dist_dir / "index.html").write_text("<!doctype html>")

    with pytest.raises(OpenError) as error:
        open_command.open_console(paths)

    assert capsys.readouterr().out.startswith("Starting the console server...")
    assert len(started) == 1
    # Its last log line, and the --port way out since it couldn't take the port.
    assert BIND_ERROR in str(error.value)
    assert "--port <a free port>" in str(error.value)
