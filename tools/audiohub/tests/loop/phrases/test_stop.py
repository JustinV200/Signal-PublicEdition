"""Tests for is_stop_command."""

import pytest

from audiohub.loop.phrases import is_stop_command


@pytest.mark.parametrize(
    "request_text",
    ["Stop.", "Cancel!", "Never mind.", "Stop now, please.", "Be quiet.", "That's enough."],
)  # fmt: skip
def test_stop_commands(request_text):
    assert is_stop_command(request_text) is True


@pytest.mark.parametrize(
    "request_text",
    ["stop the music", "cancel my meeting", "Don't stop", "", "what's the time?"],
)
def test_other_requests_are_not_stop_commands(request_text):
    assert is_stop_command(request_text) is False
