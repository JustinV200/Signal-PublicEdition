"""Shared fakes for the phone bridge tests: a socket that records what the hub sends.

Test modules can't import conftest, so the fakes and helpers come as fixtures.
"""

import asyncio
from collections.abc import Callable

import pytest

from audiohub.phone import PhoneLink


class FakeSocket:
    """Stands in for aiohttp's WebSocketResponse and records every send and close."""

    def __init__(self) -> None:
        self.sent_bytes: list[bytes] = []
        self.sent_json: list[dict] = []
        self.close_code: int | None = None

    async def send_bytes(self, data: bytes) -> None:
        self.sent_bytes.append(data)

    async def send_json(self, data) -> None:
        self.sent_json.append(data)

    async def close(self, *, code: int = 1000, message: bytes = b"") -> bool:
        self.close_code = code
        return True


async def _wait_until(predicate: Callable[[], bool], timeout_s: float = 2.0) -> None:
    """Poll until `predicate()` is true, failing the test after `timeout_s`."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


@pytest.fixture
def socket() -> FakeSocket:
    return FakeSocket()


@pytest.fixture
def link() -> PhoneLink:
    return PhoneLink()


@pytest.fixture
def wait_until() -> Callable:
    return _wait_until
