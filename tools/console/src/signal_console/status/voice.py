"""Is the voice hub (tools/audiohub) running? Read-only: a token file check and a TCP connect.

The hub writes .cache/ipc-token while its kernel listens on 127.0.0.1:8765.
Connecting and closing straight away makes the hub log nothing.
"""

import asyncio
import contextlib
from pathlib import Path

from signal_console.paths import HUB_PORT, HUB_TOKEN_PATH, LOOPBACK_HOST

CONNECT_TIMEOUT_S = 0.5


async def is_hub_listening(
    token_path: Path = HUB_TOKEN_PATH, port: int = HUB_PORT, timeout_s: float = CONNECT_TIMEOUT_S
) -> bool:
    """True when the hub's token file exists and its kernel port accepts a connection."""
    if not token_path.is_file():
        return False
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(LOOPBACK_HOST, port), timeout_s)
    except (OSError, TimeoutError):
        return False
    writer.close()
    # Closing can race the hub's own close; either way it was listening.
    with contextlib.suppress(OSError):
        await writer.wait_closed()
    return True
