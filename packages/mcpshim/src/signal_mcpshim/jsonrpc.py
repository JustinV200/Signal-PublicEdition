"""JSON-RPC 2.0 helpers for the shim: sort a line by kind and build the shim's own messages.

MCP's stdio transport is one JSON-RPC message per line. The shim relays lines as raw bytes
and only parses them to route ids, so these helpers never rewrite a relayed message.
"""

import json
from enum import Enum
from typing import Any

# JSON-RPC reserves -32000..-32099 for implementation-defined server errors.
SERVER_ERROR_CODE = -32000

JsonRpcId = str | int


class Kind(Enum):
    """What a parsed line is, which decides how the shim routes it."""

    REQUEST = "request"
    NOTIFICATION = "notification"
    RESPONSE = "response"
    OTHER = "other"


def parse(line: bytes) -> dict[str, Any] | None:
    """Parse one line into a JSON object.

    Args:
        line: the raw line, without its newline.

    Returns:
        The object, or None when the line isn't JSON or isn't an object (the shim then
        relays it untouched rather than guess at it).
    """
    try:
        message = json.loads(line)
    except ValueError:
        return None
    return message if isinstance(message, dict) else None


def message_id(message: dict[str, Any]) -> JsonRpcId | None:
    """Return the message's id when it's a usable string or integer, else None."""
    value = message.get("id")
    # bool is an int subclass, but True isn't a JSON-RPC id.
    if isinstance(value, bool) or not isinstance(value, str | int):
        return None
    return value


def kind_of(message: dict[str, Any]) -> Kind:
    """Classify a parsed message as a request, notification, response or other."""
    has_id = message_id(message) is not None
    if "method" in message:
        return Kind.REQUEST if has_id else Kind.NOTIFICATION
    return Kind.RESPONSE if has_id else Kind.OTHER


def encode(message: dict[str, Any]) -> bytes:
    """Serialize a message to one compact line (no newline)."""
    return json.dumps(message, separators=(",", ":")).encode()


def request(request_id: JsonRpcId, method: str, params: Any) -> bytes:
    """Build a request line."""
    return encode({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})


def notification(method: str) -> bytes:
    """Build a notification line with no params."""
    return encode({"jsonrpc": "2.0", "method": method})


def error_response(request_id: JsonRpcId, text: str) -> bytes:
    """Build an error response the shim sends in place of a reply the server can't give."""
    error = {"code": SERVER_ERROR_CODE, "message": text}
    return encode({"jsonrpc": "2.0", "id": request_id, "error": error})
