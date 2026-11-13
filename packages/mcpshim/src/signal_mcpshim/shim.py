"""The relay: keep the client's pipe open while the real MCP server dies and comes back.

Claude Code never restarts a dead stdio server, so it launches this shim instead. The shim
relays lines both ways, respawns the server on exit (with backoff), replays the client's
initialize to each new server, and answers requests a dead server can't. It never watches
files: a reload happens only when someone kills the server process.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

from signal_mcpshim import jsonrpc
from signal_mcpshim.child import Child
from signal_mcpshim.jsonrpc import JsonRpcId, Kind
from signal_mcpshim.timings import Backoff, ShimTimings

log = logging.getLogger("mcpshim")

INITIALIZE = "initialize"
INITIALIZED = "notifications/initialized"
REPLAY_ID_PREFIX = "mcpshim-init-"


class Shim:
    """Relay between one client and successive runs of one server command."""

    def __init__(
        self,
        command: list[str],
        write_to_client: Callable[[bytes], None],
        timings: ShimTimings | None = None,
    ) -> None:
        """Set up the relay; nothing starts until `run`.

        Args:
            command: the real server's command line.
            write_to_client: writes one line (no newline) to the client.
            timings: delays to use; the defaults suit Claude Code.
        """
        self._command = command
        self._write_to_client = write_to_client
        self._timings = timings or ShimTimings()
        self._inbox: asyncio.Queue[tuple[float, bytes | None]] = asyncio.Queue()
        self._ready = asyncio.Event()
        self._child: Child | None = None
        self._generation = 0
        self._init_params: Any = None
        self._has_init = False
        self._client_requests: dict[JsonRpcId, int] = {}  # id -> generation it went to
        self._server_requests: dict[JsonRpcId, int] = {}  # id -> generation that asked
        self._replay_id: str | None = None
        self._replay_reply: asyncio.Future[dict[str, Any]] | None = None
        self._is_stopping = False

    def feed_client_line(self, line: bytes | None) -> None:
        """Queue one line from the client (no newline); None means the client hung up.

        Must run on the shim's event loop (a reader thread uses call_soon_threadsafe).
        """
        self._inbox.put_nowait((asyncio.get_running_loop().time(), line))

    async def run(self) -> None:
        """Relay until the client hangs up, then stop the server and return."""
        supervisor = asyncio.create_task(self._supervise())
        try:
            await self._relay_client()
        finally:
            await self._shut_down(supervisor)

    async def _shut_down(self, supervisor: asyncio.Task[None]) -> None:
        """Stop the server without respawning it, then stop the supervisor."""
        self._is_stopping = True
        if self._child is not None:
            await self._child.stop(self._timings.shutdown_grace)
        supervisor.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await supervisor
        # A child spawned while we were stopping the last one; stop() is a no-op otherwise.
        if self._child is not None:
            await self._child.stop(self._timings.shutdown_grace)

    async def _supervise(self) -> None:
        """Run the server, respawning it with backoff each time it exits."""
        backoff = Backoff(self._timings)
        loop = asyncio.get_running_loop()
        while not self._is_stopping:
            started_at = loop.time()
            exit_code = await self._run_child_once_logged()
            if self._is_stopping:
                return
            uptime = loop.time() - started_at
            delay = backoff.next_delay(uptime)
            log.warning(
                "server exited (code %s) after %.1fs; respawning in %.1fs", exit_code, uptime, delay
            )
            await asyncio.sleep(delay)

    async def _run_child_once_logged(self) -> int | None:
        """Run one server; a bug in that run is logged and backed off, never fatal.

        Without this, one unexpected error (e.g. taskkill missing) would end the
        supervisor task silently and the server would never come back.
        """
        try:
            return await self._run_child_once()
        except Exception:
            log.exception("server run failed unexpectedly")
            self._ready.clear()
            self._fail_in_flight(self._generation)
        # The failed run may have left its server alive; don't let it linger beside the next.
        if self._child is not None:
            try:
                await self._child.stop(self._timings.shutdown_grace)
            except Exception:
                log.exception("couldn't stop the server after a failed run")
        return None

    async def _run_child_once(self) -> int | None:
        """Spawn one server, relay its output until it exits, and return its exit code."""
        self._generation += 1
        try:
            child = await Child.spawn(self._command)
        except OSError as error:
            log.error("can't start server %s: %s", self._command, error)
            return None
        self._child = child
        log.info("server started (pid %s)", child.pid)
        reader = asyncio.create_task(self._relay_child(child, self._generation))
        try:
            if await self._replay_initialize(child, reader):
                self._ready.set()
            await reader
        finally:
            reader.cancel()  # no-op once finished; stops late relays if the replay raised
        # No await between these two: a request is either failed here or waits for the next run.
        self._ready.clear()
        self._fail_in_flight(self._generation)
        return await child.stop(self._timings.shutdown_grace)

    async def _replay_initialize(self, child: Child, reader: asyncio.Task[None]) -> bool:
        """Repeat the client's handshake to a respawned server; True once it's usable.

        The first server needs no replay: the client's own initialize goes through to it.
        A server that dies, errors or stalls during the replay is stopped (and respawned).
        """
        if not self._has_init:
            return True
        self._replay_id = f"{REPLAY_ID_PREFIX}{self._generation}"
        self._replay_reply = asyncio.get_running_loop().create_future()
        await child.write_line(jsonrpc.request(self._replay_id, INITIALIZE, self._init_params))
        done, _ = await asyncio.wait(
            {self._replay_reply, reader},
            timeout=self._timings.ready_timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        reply = self._replay_reply.result() if self._replay_reply in done else None
        if reply is None or "error" in reply:
            log.error("replayed initialize failed: %s", reply or "no reply")
            await child.stop(self._timings.shutdown_grace)
            return False
        await child.write_line(jsonrpc.notification(INITIALIZED))
        return True

    async def _relay_child(self, child: Child, generation: int) -> None:
        """Pass the server's stdout lines to the client, tracking ids on the way."""
        async for line in child.lines():
            message = jsonrpc.parse(line)
            if message is not None and self._is_replay_reply(message):
                continue
            if message is not None:
                self._track_server_message(message, generation)
            self._write_to_client(line)

    def _is_replay_reply(self, message: dict[str, Any]) -> bool:
        """Swallow the reply to the shim's own initialize; True if `message` was it."""
        reply_id = jsonrpc.message_id(message)
        if reply_id is None or reply_id != self._replay_id or self._replay_reply is None:
            return False
        if not self._replay_reply.done():
            self._replay_reply.set_result(message)
        return True

    def _track_server_message(self, message: dict[str, Any], generation: int) -> None:
        """Forget answered client requests; remember which server asked the client what."""
        message_id = jsonrpc.message_id(message)
        kind = jsonrpc.kind_of(message)
        if kind is Kind.RESPONSE:
            self._client_requests.pop(message_id, None)
        elif kind is Kind.REQUEST:
            self._server_requests[message_id] = generation

    def _fail_in_flight(self, generation: int) -> None:
        """Answer every client request the dead server never replied to."""
        for request_id, sent_to in list(self._client_requests.items()):
            if sent_to == generation:
                del self._client_requests[request_id]
                text = "MCP server exited before replying; it is restarting, try again"
                self._write_to_client(jsonrpc.error_response(request_id, text))
        for request_id, asked_by in list(self._server_requests.items()):
            if asked_by == generation:
                del self._server_requests[request_id]

    async def _relay_client(self) -> None:
        """Pass the client's lines to the current server until the client hangs up."""
        while True:
            arrived_at, line = await self._inbox.get()
            if line is None:
                return
            message = jsonrpc.parse(line)
            if message is not None and not self._should_forward(message):
                continue
            if not await self._wait_until_ready(arrived_at):
                self._refuse(message)
                continue
            if message is not None:
                self._track_client_message(message)
            assert self._child is not None
            await self._child.write_line(line)

    def _should_forward(self, message: dict[str, Any]) -> bool:
        """Drop a client response meant for a server that has since died."""
        if jsonrpc.kind_of(message) is not Kind.RESPONSE:
            return True
        asked_by = self._server_requests.pop(jsonrpc.message_id(message), None)
        if asked_by == self._generation and self._ready.is_set():
            return True
        log.info("dropping a reply to a request from a server that has exited")
        return False

    def _track_client_message(self, message: dict[str, Any]) -> None:
        """Remember in-flight requests, and the initialize params for later replays."""
        if jsonrpc.kind_of(message) is not Kind.REQUEST:
            return
        if message.get("method") == INITIALIZE:
            self._init_params = message.get("params")
            self._has_init = True
        self._client_requests[jsonrpc.message_id(message)] = self._generation

    async def _wait_until_ready(self, arrived_at: float) -> bool:
        """Wait for a usable server, at most ready_timeout from when the line arrived."""
        if self._ready.is_set():
            return True
        remaining = arrived_at + self._timings.ready_timeout - asyncio.get_running_loop().time()
        try:
            await asyncio.wait_for(self._ready.wait(), max(remaining, 0))
        except TimeoutError:
            return False
        return True

    def _refuse(self, message: dict[str, Any] | None) -> None:
        """Answer a request that timed out waiting for a restart; drop anything else."""
        if message is not None and jsonrpc.kind_of(message) is Kind.REQUEST:
            text = "MCP server is restarting and wasn't ready in time; try again"
            self._write_to_client(jsonrpc.error_response(jsonrpc.message_id(message), text))
            return
        log.warning("server not ready; dropped a client message")
