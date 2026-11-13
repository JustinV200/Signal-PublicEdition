"""The shutdown request speaks audiohub's wire format and treats any failure as "kill it"."""

import json
import socket
import threading

import pytest

from signal_console.hub.shutdown import request_hub_shutdown

TOKEN = "hub-token"


def _serve_once(server: socket.socket, reply: bytes, received: list[dict]) -> None:
    """Accept one connection, record its request line, and send `reply`."""
    connection, _ = server.accept()
    with connection, connection.makefile("rb") as stream:
        received.append(json.loads(stream.readline()))
        connection.sendall(reply)


@pytest.mark.parametrize(
    ("reply", "has_token", "agreed"),
    [
        (b'{"ok": true}\n', True, True),
        (b'{"ok": false, "error": "missing or invalid token"}\n', True, False),
        (b"", True, False),  # the hub hung up without a reply
        (b"", False, False),  # no token file: the hub isn't listening yet
    ],
    ids=["agreed", "refused", "no-reply", "no-token"],
)
def test_request_hub_shutdown(tmp_path, reply, has_token, agreed) -> None:
    token_path = tmp_path / "ipc-token"
    if has_token:
        token_path.write_text(TOKEN, encoding="ascii")
    received: list[dict] = []
    with socket.create_server(("127.0.0.1", 0)) as server:
        thread = threading.Thread(target=_serve_once, args=(server, reply, received), daemon=True)
        if has_token:  # without a token nothing is sent, so nothing would be accepted
            thread.start()
        assert request_hub_shutdown(token_path, server.getsockname()[1]) is agreed
    if has_token:
        thread.join(5.0)
        assert received == [{"token": TOKEN, "command": "shutdown"}]
