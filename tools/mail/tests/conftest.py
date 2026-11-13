"""Shared fixtures: GmailClient's GET retries run without waiting."""

import pytest

from mail_tool.gmail import client


@pytest.fixture(autouse=True)
def no_retry_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client, "RETRY_DELAYS_S", (0.0, 0.0))
