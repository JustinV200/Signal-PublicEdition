"""Deliver text to the claimed session's Claude Code inbox (a Windows named pipe).

The console and the voice hub both send through send_to_inbox.

Documented (code.claude.com/docs/en/cross-session-messaging, "The session's
inbox socket"): on native Windows the first line must be
{"type":"auth","token":"<CLAUDE_CODE_MESSAGING_TOKEN>"}; with the session's
own token, Claude Code treats the message as its own child's and delivers it
even in bypassPermissions mode. Claude Code closes a connection whose auth
line is bad and sends nothing back on success.

NOT documented: the message line itself. The frame below is the one
Claude Code's own sender writes (read from claude.exe 2.1.301's source, then
confirmed by a probe that arrived unheld). It is an internal format and may
change between Claude Code versions; if deliveries start failing or never
arrive after an update, re-check it.
"""

import asyncio
import json

from signal_orchestrator.claim import Claim

CONNECT_TIMEOUT_S = 3.0
# How long to watch for Claude Code closing the connection (refused auth) after writing.
REJECT_WATCH_S = 0.5


class InboxError(RuntimeError):
    """The message couldn't be delivered to the inbox."""


def encode_frames(token: str, text: str) -> bytes:
    """The auth line and the message line, newline-terminated JSON (text can't break a line)."""
    auth = {"type": "auth", "token": token}
    message = {"type": "user", "message": {"role": "user", "content": text}}
    return f"{json.dumps(auth)}\n{json.dumps(message)}\n".encode()


async def send_to_inbox(claim: Claim, text: str) -> None:
    """Write one message to the claimed session's inbox.

    Args:
        claim: The orchestrator's inbox address and token.
        text: The message the orchestrator reads.

    Raises:
        InboxError: The pipe couldn't be opened, or Claude Code closed the
            connection straight away (wrong token, or a frame it rejects).
    """
    loop = asyncio.get_running_loop()
    try:
        transport, watcher = await asyncio.wait_for(
            loop.create_pipe_connection(_CloseWatcher, claim.socket), CONNECT_TIMEOUT_S
        )
    except (OSError, TimeoutError) as error:
        raise InboxError(
            f"can't open the orchestrator's inbox ({error}); is that session still open? "
            "If it was replaced, run `console claim` in the new one"
        ) from error
    try:
        transport.write(encode_frames(claim.token, text))
        if await watcher.closes_within(REJECT_WATCH_S):
            raise InboxError(
                "the orchestrator's inbox closed the connection: its token was refused "
                "(run `console claim` again) or this Claude Code version changed the format"
            )
    finally:
        transport.close()


class _CloseWatcher(asyncio.Protocol):
    """Notes when the far end closes the pipe; Claude Code sends no data back."""

    def __init__(self) -> None:
        self._closed = asyncio.get_running_loop().create_future()

    def connection_lost(self, exc: Exception | None) -> None:
        if not self._closed.done():
            self._closed.set_result(None)

    async def closes_within(self, seconds: float) -> bool:
        """True if the connection closed within `seconds`."""
        try:
            await asyncio.wait_for(asyncio.shield(self._closed), seconds)
        except TimeoutError:
            return False
        return True
