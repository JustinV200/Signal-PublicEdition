"""SessionClient: the slice of ClaudeSDKClient a managed session uses, so tests can fake it.

The real client is claude_agent_sdk.ClaudeSDKClient. In SDK 0.2.168 its
background tasks are detached (not tied to an anyio task group), so connect,
query and disconnect may be called from different asyncio tasks. Messages must
be read continuously, though: the SDK buffers only 100 messages, and a full
buffer stalls the permission callbacks that share its read loop.
"""

from collections.abc import AsyncIterator, Callable
from typing import Protocol

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, Message


class SessionClient(Protocol):
    """One Claude Code CLI process speaking the SDK's streaming protocol."""

    async def connect(self) -> None:
        """Start the CLI and open the session."""
        ...

    async def query(self, prompt: str) -> None:
        """Send one user message."""
        ...

    def receive_messages(self) -> AsyncIterator[Message]:
        """Yield every message across all turns until the CLI's output ends."""
        ...

    async def interrupt(self) -> None:
        """Stop the running turn."""
        ...

    async def disconnect(self) -> None:
        """Stop the CLI. Safe to call more than once."""
        ...


ClientFactory = Callable[[ClaudeAgentOptions], SessionClient]


def create_sdk_client(options: ClaudeAgentOptions) -> SessionClient:
    """The default ClientFactory: a real ClaudeSDKClient (not yet connected).

    Args:
        options: The session's options (see build_options).

    Returns:
        The client.
    """
    return ClaudeSDKClient(options)
