"""Tests for the kernel IPC wire format, including token authentication."""

import json

import pytest

from audiohub.kernel.ipc import MAX_LINE_BYTES, ProtocolError
from audiohub.kernel.ipc.protocol import (
    NotificationRequest,
    decode_reply,
    encode_request,
    parse_request,
)

TOKEN = "hub-token"


def line(payload, token: str | None = TOKEN) -> bytes:
    """A request line; dict payloads get the token unless `token` is None."""
    if isinstance(payload, dict) and token is not None:
        payload = {"token": token, **payload}
    return json.dumps(payload).encode() + b"\n"


@pytest.mark.parametrize(
    "request_",
    [
        NotificationRequest("build-agent", "Tests passed ✓", "high"),
        NotificationRequest("browser", "Approve Duo.", "urgent", ring_through=True),
    ],
    ids=["plain", "ring-through"],
)
def test_request_round_trips(request_) -> None:
    assert parse_request(encode_request(request_, TOKEN), TOKEN) == request_


@pytest.mark.parametrize(
    "raw",
    [
        line({"source": "a", "text": "hi"}, token=None),
        line({"source": "a", "text": "hi"}, token="wrong"),
        line({"token": 123, "source": "a", "text": "hi"}, token=None),
        line({"command": "shutdown"}, token=None),
        line({"command": "shutdown"}, token="wrong"),
        line({"source": "a", "text": "hi", "priority": "urgent", "ring_through": True}, token=None),
    ],
    ids=["missing", "wrong", "not-a-string", "shutdown-missing", "shutdown-wrong", "ring-through"],
)
def test_requests_without_the_right_token_are_rejected(raw) -> None:
    # The exact message: the token is checked before a command is even looked at.
    with pytest.raises(ProtocolError, match="missing or invalid token"):
        parse_request(raw, TOKEN)


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "hi"},
        {"source": "a", "text": "hi", "priority": "normal", "extra": True},
        {"source": "", "text": "hi"},
        {"source": "a", "text": "   "},
        {"source": "a", "text": 42},
        {"source": "a", "text": "hi", "priority": "critical"},
        {"source": "x" * 65, "text": "hi"},
        ["source", "text"],
        {"command": "reboot"},
        {"command": "shutdown", "source": "a"},
        # Only urgent notes may ring through quiet hours; others are refused, not downgraded.
        {"source": "a", "text": "hi", "priority": "high", "ring_through": True},
        {"source": "a", "text": "hi", "ring_through": True},
        {"source": "a", "text": "hi", "priority": "urgent", "ring_through": "yes"},
    ],
)
def test_invalid_requests_are_rejected(payload) -> None:
    with pytest.raises(ProtocolError):
        parse_request(line(payload), TOKEN)


def test_non_json_non_utf8_and_deep_nesting_are_rejected() -> None:
    deeply_nested = b"[" * 5000 + b"]" * 5000  # json raises RecursionError on this
    for raw in (b"hello\n", b"\xff\xfe{}\n", deeply_nested):
        with pytest.raises(ProtocolError):
            parse_request(raw, TOKEN)


def test_oversized_lines_are_rejected_both_ways() -> None:
    with pytest.raises(ProtocolError, match="limit"):
        encode_request(NotificationRequest("a", "x" * MAX_LINE_BYTES), TOKEN)
    with pytest.raises(ProtocolError):
        parse_request(b"x" * (MAX_LINE_BYTES + 1), TOKEN)


def test_reply_needs_boolean_ok() -> None:
    assert decode_reply(line({"ok": True, "id": "m1"}, token=None))["id"] == "m1"
    with pytest.raises(ProtocolError):
        decode_reply(line({"ok": "yes"}, token=None))
