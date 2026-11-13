"""The Sonnet connection behind the dispatcher: one persistent, tool-less SDK session.

Measured on this machine (real dispatcher prompt, thinking off): a fresh
`query()` per decision took 5-7 s, because each one spawns the bundled CLI and
pays a slow first turn. A persistent `ClaudeSDKClient` answers in about 2.2 s
after a warm-up turn. So the backend keeps one session open, warms it up when
it connects, and replaces it every `RESET_EVERY_DECISIONS` decisions so the
conversation (and its cost) never grows large. A replacement is connected in
the background, so no decision waits for it.

Connect plus warm-up is capped at `CONNECT_TIMEOUT_S`. A failed or timed-out
connect is discarded, so the next call starts a fresh one; meanwhile the
dispatcher's own timeout makes decisions fall back.
"""

import asyncio
import logging
from typing import Protocol

from claude_agent_sdk import ClaudeSDKClient

from .sdk_session import BackendError, ask_turn, disconnect_quietly, session_options

logger = logging.getLogger(__name__)

# TODO: move these tunables to KernelSettings once audiohub.config is free to edit.
RESET_EVERY_DECISIONS = 10
CONNECT_TIMEOUT_S = 20.0  # connect + warm-up measured at 3-4 s
WARM_UP_PROMPT = 'This is a connection check. Reply with exactly {"decisions": []}'


class DispatcherBackend(Protocol):
    """Anything that can answer one dispatcher request with raw model text."""

    async def start(self) -> None:
        """Get ready to answer (connect, warm up); may be a no-op."""
        ...

    async def complete(self, prompt: str) -> str:
        """Send `prompt` as one user turn and return the model's full text reply."""
        ...

    async def close(self) -> None:
        """Release any connection held by the backend."""
        ...


class BackendClosedError(BackendError):
    """The backend was used after `close()`."""


class SonnetBackend:
    """A `DispatcherBackend` backed by a persistent Claude Agent SDK session."""

    def __init__(
        self, model: str, system_prompt: str, reset_every: int = RESET_EVERY_DECISIONS
    ) -> None:
        """Configure the backend; nothing connects until `start` or the first call.

        Args:
            model: Model alias or id, e.g. "sonnet".
            system_prompt: The dispatcher's system prompt.
            reset_every: Decisions per session before it is replaced.
        """
        self._options = session_options(model, system_prompt)
        self._reset_every = reset_every
        self._lock = asyncio.Lock()
        self._client_task: asyncio.Task[ClaudeSDKClient] | None = None
        self._uses = 0
        self._is_closed = False
        # Strong references to background disconnects so they aren't garbage-collected.
        self._closing: set[asyncio.Task[None]] = set()

    async def start(self) -> None:
        """Connect and warm up now, so the first real decision is fast.

        Raises:
            BackendClosedError: If the backend was closed.
            TimeoutError: If connecting took longer than `CONNECT_TIMEOUT_S`.
            Exception: Whatever the SDK raises when it can't connect.
        """
        self._raise_if_closed()
        await self._await_connect()

    async def complete(self, prompt: str) -> str:
        """Ask Sonnet one dispatcher request and return its text reply.

        Raises:
            BackendClosedError: If the backend was closed.
            BackendError: If the session reports an error result.
            Exception: SDK connection errors. After any failure, including
                cancellation by a timeout, the session is replaced, so a late
                reply can never leak into the next decision.
        """
        async with self._lock:
            self._raise_if_closed()
            client = await self._await_connect()
            try:
                reply = await ask_turn(client, prompt)
            except BaseException:
                self._replace_session()
                raise
            self._uses += 1
            if self._uses >= self._reset_every:
                self._replace_session()
            return reply

    async def close(self) -> None:
        """Refuse further calls, disconnect the session and wait for pending disconnects."""
        self._is_closed = True  # set before the lock so new calls fail at once
        async with self._lock:
            self._discard_session()
            if self._closing:
                await asyncio.gather(*self._closing, return_exceptions=True)

    def _raise_if_closed(self) -> None:
        if self._is_closed:
            raise BackendClosedError("the dispatcher backend is closed")

    async def _await_connect(self) -> ClaudeSDKClient:
        """Wait for the current session's connect, discarding it if it failed."""
        task = self._ensure_client_task()
        try:
            # shield: a caller's timeout must not cancel a connect later calls share.
            return await asyncio.shield(task)
        except BaseException:
            # A finished task means the connect itself failed or timed out:
            # forget it so the next call starts afresh. An unfinished one means
            # only our caller gave up, and the connect carries on for later.
            if task.done() and self._client_task is task:
                self._client_task = None
            raise

    def _ensure_client_task(self) -> asyncio.Task[ClaudeSDKClient]:
        """Return the task that connects the current session, starting one if needed."""
        task = self._client_task
        # A background connect that already failed is retried rather than reused.
        if task is None or (task.done() and (task.cancelled() or task.exception())):
            task = asyncio.create_task(self._connect())
            self._client_task = task
        return task

    async def _connect(self) -> ClaudeSDKClient:
        """Open a session and run the warm-up turn, within `CONNECT_TIMEOUT_S`."""
        client = ClaudeSDKClient(self._options)
        try:
            async with asyncio.timeout(CONNECT_TIMEOUT_S):
                await client.connect()
                await ask_turn(client, WARM_UP_PROMPT)
        except BaseException:
            await disconnect_quietly(client)
            raise
        logger.info("dispatcher session connected and warmed up")
        return client

    def _replace_session(self) -> None:
        """Drop the current session and start connecting its replacement."""
        self._discard_session()
        self._ensure_client_task()

    def _discard_session(self) -> None:
        """Forget the current session and disconnect it in the background."""
        task, self._client_task, self._uses = self._client_task, None, 0
        if task is None:
            return
        closer = asyncio.create_task(_disconnect_when_ready(task))
        self._closing.add(closer)
        closer.add_done_callback(self._closing.discard)


async def _disconnect_when_ready(task: asyncio.Task[ClaudeSDKClient]) -> None:
    """Disconnect a session once its connect task settles; a failed connect needs nothing."""
    if not task.done():
        task.cancel()
    # asyncio.wait never raises the task's own error, so only a cancellation of
    # this closer itself propagates from here.
    await asyncio.wait([task])
    if task.cancelled():
        return
    if task.exception() is not None:
        # Whoever awaited the connect already saw this error; note it and move on.
        logger.debug("discarded dispatcher session had failed to connect: %s", task.exception())
        return
    await disconnect_quietly(task.result())
