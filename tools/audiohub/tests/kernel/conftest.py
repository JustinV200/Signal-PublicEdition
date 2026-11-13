"""Shared fixtures for kernel tests: a scripted dispatcher backend and message builders.

Nothing here touches the network; `FakeBackend` stands in for Sonnet.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest

from audiohub.config import KernelSettings
from audiohub.kernel import OutboundMessage

NOW = 1_000_000.0


class FakeBackend:
    """A `DispatcherBackend` that answers from a script instead of Sonnet.

    Each queued reply is a string (returned as is), an exception (raised), or
    a callable taking the prompt and returning a string. With nothing queued
    it delivers every pending message in the order the request lists them.
    """

    def __init__(self) -> None:
        self.replies: list[Any] = []
        self.prompts: list[str] = []
        self.delay_s = 0.0
        self.started = False
        self.closed = False

    def respond(self, *decisions: dict[str, Any]) -> None:
        """Queue one reply made of these decision entries."""
        self.replies.append(json.dumps({"decisions": list(decisions)}))

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        reply = self.replies.pop(0) if self.replies else deliver_all
        if isinstance(reply, BaseException):
            raise reply
        return reply(prompt) if callable(reply) else reply

    def last_request(self) -> dict[str, Any]:
        """The JSON object of the most recent request."""
        return request_payload(self.prompts[-1])


def request_payload(prompt: str) -> dict[str, Any]:
    """Extract the JSON object that follows the instruction line of a request."""
    return json.loads(prompt.split("\n", 1)[1])


def deliver_all(prompt: str) -> str:
    """A reply that delivers every pending message verbatim, in request order."""
    pending = request_payload(prompt)["pending"]
    entries = [{"id": m["id"], "action": "deliver", "text": None, "reason": "ok"} for m in pending]
    return json.dumps({"decisions": entries})


def build_entry(message_id: str, action: str, text: str | None = None, reason: str = "r") -> dict:
    """One decision entry as Sonnet would write it."""
    return {"id": message_id, "action": action, "text": text, "reason": reason}


@pytest.fixture
def entry() -> Callable[..., dict]:
    """The `build_entry` helper (test modules can't import conftest directly)."""
    return build_entry


@pytest.fixture
def fake_backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
def kernel_settings() -> KernelSettings:
    # Short timings keep timeout and re-check tests fast.
    return KernelSettings(max_spoken_words=80, hold_recheck_s=0.05, decision_timeout_s=0.5)


@pytest.fixture
def make_message() -> Callable[..., OutboundMessage]:
    """Build an `OutboundMessage` with a chosen id and sensible defaults."""

    def build(
        message_id: str,
        priority: str = "normal",
        text: str = "hello there",
        source: str = "agent",
        age_s: float = 0.0,
        is_direct_reply: bool = False,
    ) -> OutboundMessage:
        created_at = NOW - age_s
        return OutboundMessage(message_id, source, text, priority, created_at, is_direct_reply)

    return build
