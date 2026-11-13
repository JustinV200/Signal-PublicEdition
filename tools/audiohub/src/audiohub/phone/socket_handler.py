"""The phone WebSocket's message loop: mic audio and acks in, until close or the first bad frame.

PhoneServer calls `serve_phone_socket` once a handshake has passed its cookie,
Host and Origin checks. The socket is attached to the PhoneLink (replacing any
older phone) and every message goes to the link. A message that breaks the
protocol (see protocol.py) closes the socket with a policy-violation code,
and aiohttp itself closes one that is over MAX_MIC_BYTES. Pings every
HEARTBEAT_S notice a phone that went to sleep without closing.
"""

import logging

from aiohttp import WSCloseCode, WSMessage, WSMsgType, web

from .link import PhoneLink
from .protocol import MAX_MIC_BYTES, FrameError

logger = logging.getLogger(__name__)

# A phone that misses a pong for half of this is treated as gone.
HEARTBEAT_S = 10.0


async def serve_phone_socket(request: web.Request, link: PhoneLink) -> web.WebSocketResponse:
    """Accept the phone socket and feed its messages to `link` until it closes.

    Args:
        request: The authenticated handshake request.
        link: Where the socket is attached and its messages go.

    Returns:
        The finished WebSocket response.
    """
    # PCM barely compresses, so per-message deflate would only add latency.
    socket = web.WebSocketResponse(
        max_msg_size=MAX_MIC_BYTES, heartbeat=HEARTBEAT_S, compress=False
    )
    await socket.prepare(request)
    logger.info("phone connected")
    try:
        await link.attach(socket)
        async for message in socket:
            problem = _deliver(link, message)
            if problem is not None:
                logger.warning("closing the phone socket after a bad message: %s", problem)
                await socket.close(code=WSCloseCode.POLICY_VIOLATION, message=b"bad message")
                break
    except ConnectionError as error:
        logger.info("phone connection lost: %s", error)
    finally:
        link.detach(socket)
        logger.info("phone disconnected")
    return socket


def _deliver(link: PhoneLink, message: WSMessage) -> str | None:
    """Hand one message to the link; return why it is invalid, or None if it was fine."""
    try:
        if message.type == WSMsgType.BINARY:
            link.receive_audio(message.data)
        elif message.type == WSMsgType.TEXT:
            link.receive_control(message.data)
        else:
            # ERROR covers an oversized message, which aiohttp has already refused.
            return f"unexpected {message.type.name} message"
    except FrameError as error:
        return str(error)
    return None
