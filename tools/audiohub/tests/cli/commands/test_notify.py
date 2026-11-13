"""Tests for `audiohub notify`, with the kernel client replaced by a recording fake."""

import pytest

from audiohub.cli import main
from audiohub.cli.commands import notify
from audiohub.config import loader
from audiohub.kernel import HubNotRunningError


class RecordingSender:
    """Stands in for `send_notification`: records calls, returns "m7" or raises `error`."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.error: Exception | None = None

    def __call__(self, host, port, source, text, priority) -> str:
        self.calls.append((host, port, source, text, priority))
        if self.error is not None:
            raise self.error
        return "m7"


@pytest.fixture(autouse=True)
def no_local_config(tmp_path, monkeypatch):
    # Keep a real tools/audiohub/audiohub.toml from changing these tests.
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")


@pytest.fixture
def sender(monkeypatch) -> RecordingSender:
    fake = RecordingSender()
    monkeypatch.setattr(notify, "send_notification", fake)
    return fake


def test_sends_text_with_source_and_priority(sender, capsys):
    assert main(["notify", "Deploy done.", "--source", "deployer", "--priority", "high"]) == 0
    assert sender.calls == [("127.0.0.1", 8765, "deployer", "Deploy done.", "high")]
    assert "m7" in capsys.readouterr().out


def test_hub_not_running_exits_1_with_one_line_error(sender, capsys):
    sender.error = HubNotRunningError("audiohub isn't running on 127.0.0.1:8765")
    assert main(["notify", "Hello."]) == notify.EXIT_NOT_DELIVERED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == (
        "audiohub: error: message not delivered: audiohub isn't running on 127.0.0.1:8765"
    )
