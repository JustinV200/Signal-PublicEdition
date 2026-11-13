"""call_in_thread: run one blocking brief call off the event loop, with readable errors.

The log's lock can wait up to 2 s, so every tool's work runs in a worker thread.
Expected failures (bad arguments, a busy or unwritable state) become ToolError, so
the model gets the message instead of a crash.
"""

import asyncio
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver.exceptions import ToolError
from signal_brief import BriefLogError


async def call_in_thread[Result](function: Callable[..., Result], *args: Any) -> Result:
    """`function(*args)` in a worker thread.

    Raises:
        ToolError: It raised ValueError or BriefLogError.
    """
    try:
        return await asyncio.to_thread(function, *args)
    except (ValueError, BriefLogError) as error:
        raise ToolError(str(error)) from error
