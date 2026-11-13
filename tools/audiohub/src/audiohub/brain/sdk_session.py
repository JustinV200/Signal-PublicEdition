"""SdkSession: the brain's one persistent ClaudeSDKClient, behind a small SDK-neutral API.

Part of the thin SDK adapter. ClaudeBrain only sees connect/send/events/
interrupt/set_model/disconnect, the session id and session events, so tests
swap this class for a fake.
"""

import dataclasses
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

from audiohub.brain.events import SessionEvent
from audiohub.brain.handoff_tool import HandOff
from audiohub.brain.permissions import PermissionDecider
from audiohub.brain.sdk_messages import MessageTranslator
from audiohub.brain.sdk_options import build_options
from audiohub.config import BrainSettings

logger = logging.getLogger(__name__)

ClientFactory = Callable[[ClaudeAgentOptions], ClaudeSDKClient]


class SdkSession:
    """One multi-turn Claude Code session run by the bundled CLI.

    The SDK requires every call on a connected client to happen in the same
    async context (event loop and task group) that called connect().
    """

    # Five parameters, one over the usual limit: client_factory is a test seam.
    def __init__(
        self,
        brain_settings: BrainSettings,
        cwd: Path,
        decide_permission: PermissionDecider,
        hand_off: HandOff,
        client_factory: ClientFactory = ClaudeSDKClient,
    ) -> None:
        """Prepare the session. Nothing starts until connect().

        Args:
            brain_settings: Model and effort for the session.
            cwd: Working directory for Claude Code, normally the repo root.
            decide_permission: Called for tool calls the CLI would prompt for.
            hand_off: Runs the hand-off tool.
            client_factory: Builds the SDK client; tests pass a fake.
        """
        self._options = build_options(brain_settings, cwd, decide_permission, hand_off)
        self._client_factory = client_factory
        self._client: ClaudeSDKClient | None = None
        self._translator = MessageTranslator()
        self._session_id: str | None = None

    @property
    def session_id(self) -> str | None:
        """The CLI's id for this conversation, from its latest turn result; None before one."""
        return self._session_id

    async def connect(self, resume: str | None = None) -> None:
        """Start the CLI subprocess and open the session.

        Args:
            resume: A conversation id to carry on (`--resume`), so a reconnect
                (for a new effort, which the CLI only takes at start) keeps the
                conversation. None starts a new one.

        Raises:
            claude_agent_sdk.ClaudeSDKError: The CLI couldn't start or initialise
                (for example, missing login).
        """
        options = dataclasses.replace(self._options, resume=resume)
        client = self._client_factory(options)
        await client.connect()
        self._client = client
        self._session_id = resume
        logger.info(
            "Claude session connected (model=%s, effort=%s, resume=%s, cwd=%s, settings=%s)",
            options.model,
            options.effort,
            resume or "no",
            options.cwd,
            ",".join(options.setting_sources or []),
        )

    async def set_model(self, model: str) -> None:
        """Switch the model live, from the next turn on (the SDK's set_model control request).

        Raises:
            RuntimeError: The session isn't connected.
            claude_agent_sdk.ClaudeSDKError: The CLI refused or the request failed.
        """
        await self._require_client().set_model(model)

    async def mcp_server_statuses(self) -> dict[str, str]:
        """Each MCP server's name and status, from the CLI's mcp_status control request.

        Raises:
            RuntimeError: The session isn't connected.
            Exception: The control request failed (the SDK raises plain Exception).
        """
        reply = await self._require_client().get_mcp_status()
        servers = reply.get("mcpServers", [])
        return {server["name"]: server["status"] for server in servers}

    async def reconnect_mcp_server(self, name: str) -> None:
        """Reconnect one MCP server (the CLI's mcp_reconnect control request).

        Raises:
            RuntimeError: The session isn't connected.
            Exception: The reconnect failed.
        """
        await self._require_client().reconnect_mcp_server(name)

    async def disconnect(self) -> None:
        """Close the session and stop the CLI. Safe to call when not connected."""
        if self._client is None:
            return
        client, self._client = self._client, None
        await client.disconnect()

    async def send(self, text: str) -> None:
        """Send one user message, starting a turn.

        Args:
            text: What the user said.

        Raises:
            RuntimeError: The session isn't connected.
        """
        await self._require_client().query(text)

    async def events(self) -> AsyncIterator[SessionEvent]:
        """Yield every event of the session, across all turns, until the CLI's stream ends.

        Meant for one long-lived reader. Reading continuously also keeps the SDK's
        bounded message buffer from filling up between turns, which would stall
        the permission callbacks that share its read loop.

        Yields:
            ReplyText per spoken text block, TurnActivity for other assistant and
            user messages (tool calls, tool results, thinking, subagents),
            TurnDone at the end of each turn we started, and InjectedTurnDone at
            the end of each turn the CLI injected.

        Raises:
            RuntimeError: The session isn't connected.
            claude_agent_sdk.ClaudeSDKError: The CLI failed mid-session.
        """
        async for message in self._require_client().receive_messages():
            if isinstance(message, ResultMessage):
                self._session_id = message.session_id  # what a reconnect resumes
            for event in self._translator.translate(message):
                yield event

    async def interrupt(self) -> None:
        """Ask the CLI to stop the running turn. The turn then ends with an error TurnDone.

        Raises:
            RuntimeError: The session isn't connected.
        """
        await self._require_client().interrupt()

    def _require_client(self) -> ClaudeSDKClient:
        """Return the connected client, or raise if connect() hasn't run."""
        if self._client is None:
            raise RuntimeError("The Claude session isn't connected; call connect() first.")
        return self._client
