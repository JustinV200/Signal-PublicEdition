"""The fill step swallows Playwright-style errors that quote the secret, and re-raises
cancellation without any chained context."""

import asyncio

import pytest

from vault.fill.safe_fill import fill_without_leaks
from vault.secret import Secret

SECRET = "S3cret-Pa55word!"


class _LeakyHandle:
    """Fails the way Playwright does: the error message quotes fill("<value>")."""

    def __init__(self, cancel: bool = False) -> None:
        self._cancel = cancel

    async def fill(self, value: str, *, timeout: float | None = None) -> None:
        try:
            raise TimeoutError(f'ElementHandle.fill: Timeout\nCall log:\n  - fill("{value}")')
        except TimeoutError:
            if self._cancel:
                # Cancelled while handling the leaky error: its __context__ is that error.
                raise asyncio.CancelledError() from None
            raise


@pytest.mark.asyncio
async def test_a_failing_fill_returns_false_without_raising():
    assert await fill_without_leaks([(_LeakyHandle(), Secret(SECRET))]) is False


@pytest.mark.asyncio
async def test_cancellation_is_reraised_fresh_with_no_context():
    with pytest.raises(asyncio.CancelledError) as raised:
        await fill_without_leaks([(_LeakyHandle(cancel=True), Secret(SECRET))])

    assert raised.value.__context__ is None
    assert raised.value.__cause__ is None
    assert SECRET not in str(raised.value)
