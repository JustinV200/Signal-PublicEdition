"""Tests for Notifier: a hub that is down is logged and skipped, never raised."""

import asyncio
import logging
import socket
from pathlib import Path

import pytest

from signal_hub_notify import (
    Delivery,
    DeliveryStatus,
    HubDroppedError,
    HubNote,
    HubRejectedError,
    Notifier,
)


@pytest.mark.asyncio
async def test_notifier_logs_and_carries_on_when_the_hub_is_down(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    token_file = tmp_path / "ipc-token"
    token_file.write_text("hub-secret", encoding="ascii")
    # Down twice over: nothing listens, and then the hub's token file is gone too.
    notifier = Notifier("127.0.0.1", closed_port, token_file)

    with caplog.at_level(logging.INFO):
        first = await notifier.post(HubNote("session:Signal", "Finished.", "normal"))
        token_file.unlink()
        second = await notifier.post(HubNote("session:Signal", "Finished again.", "normal"))

    assert first == second == Delivery(DeliveryStatus.NO_HUB)
    assert caplog.text.count("Voice hub not running") == 2


@pytest.mark.asyncio
async def test_notifier_reads_the_token_file_at_each_delivery(tmp_path: Path) -> None:
    sent: list[tuple[HubNote, str]] = []

    async def fake_send(host: str, port: int, note: HubNote, token: str) -> str:
        sent.append((note, token))
        return "m1"

    token_file = tmp_path / "ipc-token"
    token_file.write_text("first\n", encoding="ascii")
    notifier = Notifier("127.0.0.1", 1, token_file, send=fake_send)

    notifier.post(HubNote("browser", "One."))
    await notifier.drain()
    # The hub restarted and published a new token.
    token_file.write_text("second", encoding="ascii")
    notifier.post(HubNote("browser", "Two."))
    await notifier.drain()

    assert [token for _, token in sent] == ["first", "second"]


@pytest.mark.asyncio
async def test_drain_returns_when_a_finished_note_is_not_yet_forgotten(tmp_path: Path) -> None:
    # Regression: drain() spun forever (never yielding, so the test would hang) when a
    # note's task had finished but its done callback hadn't removed it from the set yet.
    async def instant_send(host: str, port: int, note: HubNote, token: str) -> str:
        return "m1"

    token_file = tmp_path / "ipc-token"
    token_file.write_text("token", encoding="ascii")
    notifier = Notifier("127.0.0.1", 1, token_file, send=instant_send)

    notifier.post(HubNote("browser", "One."))
    # One loop turn: the delivery finishes; its done callback is only scheduled.
    await asyncio.sleep(0)
    await notifier.drain()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ("m1", Delivery(DeliveryStatus.SPOKEN)),
        (
            HubDroppedError("the owner is away"),
            Delivery(DeliveryStatus.DROPPED, "the owner is away"),
        ),
        (HubRejectedError("bad token"), Delivery(DeliveryStatus.FAILED)),
        (TimeoutError(), Delivery(DeliveryStatus.FAILED)),
    ],
    ids=["spoken", "dropped", "rejected", "timeout"],
)
async def test_post_returns_a_handle_to_the_delivery_which_never_raises(
    tmp_path: Path, outcome: str | Exception, expected: Delivery
) -> None:
    async def fake_send(host: str, port: int, note: HubNote, token: str) -> str:
        if isinstance(outcome, Exception):
            raise outcome
        return str(outcome)

    token_file = tmp_path / "ipc-token"
    token_file.write_text("token", encoding="ascii")
    notifier = Notifier("127.0.0.1", 1, token_file, send=fake_send)

    assert await notifier.post(HubNote("browser", "Duo push.", "urgent")) == expected
