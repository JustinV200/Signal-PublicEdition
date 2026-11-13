"""Run several coroutines together and stop them all as one unit (a loop building block).

The conversation runs its loops (hearing, brain turns, speech) side by side
and starts its models in parallel. If one fails, the rest are cancelled and
that failure is raised as itself, not wrapped in an ExceptionGroup. That way
the CLI's handling of AudioStreamError and friends still applies.
"""

import asyncio
import logging
from collections.abc import Coroutine, Iterable
from typing import Any, Literal

logger = logging.getLogger(__name__)

ReturnWhen = Literal["FIRST_COMPLETED", "FIRST_EXCEPTION"]


async def run_tasks(
    coroutines: Iterable[Coroutine[Any, Any, Any]], return_when: ReturnWhen
) -> None:
    """Run coroutines as tasks until `return_when`, then cancel whatever is left.

    Args:
        coroutines: What to run.
        return_when: asyncio.FIRST_COMPLETED stops everything as soon as one
            finishes; asyncio.FIRST_EXCEPTION waits for all of them unless one fails.

    Raises:
        Exception: The first failure among the tasks, in the order given.
        asyncio.CancelledError: If this call itself is cancelled (Ctrl+C);
            every task is cancelled and awaited first.
    """
    tasks = [asyncio.create_task(coroutine) for coroutine in coroutines]
    if not tasks:
        return
    try:
        await asyncio.wait(tasks, return_when=return_when)
    finally:
        await _cancel_and_wait(tasks)
    # Every task has finished now. A cancelled one has no exception to read;
    # one that failed during its cleanup does, and is reported too.
    failures = [task.exception() for task in tasks if not task.cancelled()]
    errors = [error for error in failures if error is not None]
    for extra in errors[1:]:
        logger.error("another task failed too", exc_info=extra)
    if errors:
        raise errors[0]


async def _cancel_and_wait(tasks: list[asyncio.Task[Any]]) -> None:
    for task in tasks:
        task.cancel()
    # return_exceptions keeps one task's failure from hiding the others'
    # cleanup; the failures themselves are read off the tasks by the caller.
    await asyncio.gather(*tasks, return_exceptions=True)
