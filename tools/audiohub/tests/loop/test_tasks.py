"""Tests for run_tasks: a failure surfaces as itself and the other tasks are cancelled."""

import asyncio

import pytest

from audiohub.audio import AudioStreamError
from audiohub.loop.tasks import run_tasks


@pytest.mark.asyncio
async def test_first_failure_is_raised_unwrapped_and_the_rest_cancelled():
    was_cancelled = asyncio.Event()

    async def forever():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            was_cancelled.set()
            raise

    async def failing():
        raise AudioStreamError("mic unplugged")

    with pytest.raises(AudioStreamError, match="mic unplugged"):
        await run_tasks([forever(), failing()], asyncio.FIRST_COMPLETED)
    assert was_cancelled.is_set()
