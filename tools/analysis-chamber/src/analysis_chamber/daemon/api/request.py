"""read_request: parse one HTTP/1.1 request off a stream, strictly, with size caps.

Only what the chamber client sends is accepted: `POST <path> HTTP/1.1`, a
Content-Length body of JSON object, and a Bearer token. Anything else raises
BadRequest, and the server then closes the connection without a reply (coding
rule 7: any web page can reach localhost).
"""

import asyncio
import hmac
import json
from dataclasses import dataclass
from typing import Any

MAX_LINE_BYTES = 8 * 1024
MAX_HEADERS = 50
MAX_BODY_BYTES = 256 * 1024
BEARER_PREFIX = "Bearer "
REQUEST_LINE_PARTS = 3  # method, path, version


class BadRequest(Exception):
    """The request is malformed, too big or not what the chamber client sends."""


@dataclass(frozen=True)
class Request:
    """A parsed request.

    Attributes:
        path: The route, e.g. "/start".
        body: The JSON body (always an object).
    """

    path: str
    body: dict[str, Any]


async def read_request(reader: asyncio.StreamReader, token: bytes) -> Request:
    """Read and parse one request, checking its token in constant time.

    Args:
        reader: The connection's stream.
        token: The daemon's token (ASCII bytes).

    Raises:
        BadRequest: Anything malformed, oversized or missing.
        asyncio.IncompleteReadError: The client hung up mid-request.
    """
    parts = (await _read_line(reader)).split(" ")
    if len(parts) != REQUEST_LINE_PARTS:
        raise BadRequest("malformed request line")
    method, path, version = parts
    if method != "POST" or version != "HTTP/1.1" or not path.startswith("/"):
        raise BadRequest("not a POST HTTP/1.1 request")
    headers = await _read_headers(reader)
    # Check the token before reading the body, so an unauthenticated client can't make us buffer it.
    authorization = headers.get("authorization", "")
    given = authorization.removeprefix(BEARER_PREFIX).encode()
    if not authorization.startswith(BEARER_PREFIX) or not hmac.compare_digest(given, token):
        raise BadRequest("missing or wrong bearer token")
    body = await _read_body(reader, headers.get("content-length", ""))
    return Request(path, body)


async def _read_line(reader: asyncio.StreamReader) -> str:
    try:
        raw = await reader.readuntil(b"\r\n")
    except asyncio.LimitOverrunError as error:
        raise BadRequest("line too long") from error
    if len(raw) > MAX_LINE_BYTES:
        raise BadRequest("line too long")
    try:
        return raw[:-2].decode("ascii")
    except UnicodeDecodeError as error:
        raise BadRequest("non-ASCII header") from error


async def _read_headers(reader: asyncio.StreamReader) -> dict[str, str]:
    headers: dict[str, str] = {}
    for _ in range(MAX_HEADERS):
        line = await _read_line(reader)
        if not line:
            return headers
        name, separator, value = line.partition(":")
        if not separator:
            raise BadRequest("malformed header")
        headers[name.strip().lower()] = value.strip()
    raise BadRequest("too many headers")


async def _read_body(reader: asyncio.StreamReader, length_text: str) -> dict[str, Any]:
    if not length_text.isdigit() or int(length_text) > MAX_BODY_BYTES:
        raise BadRequest("missing or oversized Content-Length")
    raw = await reader.readexactly(int(length_text))
    try:
        body = json.loads(raw)
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise BadRequest("body isn't JSON") from error
    if not isinstance(body, dict):
        raise BadRequest("body isn't a JSON object")
    return body
