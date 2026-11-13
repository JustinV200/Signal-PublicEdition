"""A saved claim counts only if its socket is a local named pipe: the token is written there."""

import json

import pytest

from signal_orchestrator import Claim, claim_to_json, read_claim_file


@pytest.mark.parametrize(
    ("socket", "is_kept"),
    [
        (r"\\.\pipe\LOCAL\cc-msg-1", True),
        (r"\\server\share\inbox", False),
        (r"C:\Users\me\inbox.txt", False),
        (r"\\.\pipe\..\C:\Users\me\inbox.txt", False),
    ],
)
def test_read_claim_file_refuses_a_socket_that_isnt_a_local_pipe(tmp_path, socket, is_kept):
    path = tmp_path / "orchestrator.json"
    path.write_text(json.dumps(claim_to_json(Claim(socket, "tok", None, ""))), encoding="utf-8")

    claim = read_claim_file(path)

    assert (claim is not None and claim.socket == socket) is is_kept
