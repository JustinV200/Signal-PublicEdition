"""`audiohub check` tells a running hub from an installed one that isn't running."""

import json
import socket

from audiohub.cli.hub_check import is_hub_running


def test_running_needs_both_the_token_file_and_a_listener(tmp_path):
    token = tmp_path / "ipc-token"
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
        assert not is_hub_running("127.0.0.1", port, token)  # listener, no token
        token.write_text("t")
        assert is_hub_running("127.0.0.1", port, token)
    assert not is_hub_running("127.0.0.1", port, token)  # token left behind, hub gone


def test_check_command_reads_not_running_as_a_passing_summary(monkeypatch, capsys):
    from audiohub.cli import hub_check, main

    monkeypatch.setattr(hub_check, "is_hub_running", lambda *a: False)
    assert main(["check"]) == 0
    summary = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert "isn't running" in summary["words"] and summary["command"]
