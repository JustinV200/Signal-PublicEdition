"""Wire format between the sessions daemon and its clients (CLI, MCP server).

Newline-delimited UTF-8 JSON over loopback TCP. A request is
{"op": "<name>", "args": {...}, "token": "<secret>"}; a reply is
{"ok": true, "result": ...} or {"ok": false, "error": "<why>"}. The token
(from the daemon's token file) is checked first, so a caller without it
learns nothing else. Both sides validate requests with the same rules (known
op, exact argument names and types, size caps, allowed permission modes), so
a bad request fails before it is even sent.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from claude_sessions.approvals import validate_permission_mode
from claude_sessions.tokens import tokens_match

ENCODING = "utf-8"
LINE_END = b"\n"
# Prompts can be long task descriptions and status replies carry several
# assistant texts, but nothing legitimate comes close to 1 MiB.
MAX_LINE_BYTES = 1024 * 1024
MAX_PROMPT_CHARS = 100_000
MAX_PATH_CHARS = 1024
MAX_NAME_CHARS = 100
# Status shows at most this many assistant texts; the daemon keeps as many.
MAX_STATUS_TEXTS = 10
# Managed ids ("s-1a2b3c4d") and Claude session UUIDs both fit this shape.
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


class ProtocolError(ValueError):
    """A request or reply that breaks the wire format."""


class AuthError(ProtocolError):
    """A request without the daemon's token, or with a wrong one."""


@dataclass(frozen=True)
class ArgSpec:
    """One argument an op accepts."""

    name: str
    kind: type
    is_required: bool = True
    max_chars: int | None = None


@dataclass(frozen=True)
class Request:
    """A validated request: the op name and its arguments."""

    op: str
    args: dict[str, Any]


_ID = ArgSpec("id", str, max_chars=64)
_PROMPT = ArgSpec("prompt", str, max_chars=MAX_PROMPT_CHARS)
OPS: dict[str, tuple[ArgSpec, ...]] = {
    "ping": (),
    "list": (),
    "shutdown": (),
    "start": (
        ArgSpec("repo", str, max_chars=MAX_PATH_CHARS),
        _PROMPT,
        ArgSpec("model", str, is_required=False, max_chars=MAX_NAME_CHARS),
        ArgSpec("permission_mode", str, is_required=False, max_chars=MAX_NAME_CHARS),
    ),
    "send": (_ID, _PROMPT),
    "status": (_ID, ArgSpec("last_n", int, is_required=False)),
    "resume": (ArgSpec("session", str, max_chars=64), _PROMPT),
    "stop": (_ID,),
}


def validate_request(op: Any, args: Any) -> Request:
    """Check an op and its arguments against OPS.

    Raises:
        ProtocolError: Unknown op, unknown/missing arguments, wrong types,
            blank or oversized strings, a malformed id, or last_n out of range.
        PermissionModeError: permission_mode isn't allowed (bypassPermissions never is).
    """
    if not isinstance(op, str) or op not in OPS:
        raise ProtocolError(f"unknown op {op!r}; expected one of {', '.join(OPS)}")
    if not isinstance(args, dict):
        raise ProtocolError('"args" must be a JSON object')
    specs = {spec.name: spec for spec in OPS[op]}
    unknown = set(args) - set(specs)
    if unknown:
        raise ProtocolError(f"{op} doesn't take {', '.join(sorted(unknown))}")
    for spec in specs.values():
        _check_arg(op, spec, args)
    _check_values(args)
    return Request(op, dict(args))


def encode_request(op: str, args: dict[str, Any] | None, token: str) -> bytes:
    """Validate and serialize one request line carrying the token (see validate_request)."""
    request = validate_request(op, args or {})
    return encode_line({"op": request.op, "args": request.args, "token": token})


def parse_request(line: bytes, expected_token: str) -> Request:
    """Decode, authenticate and validate one request line received by the daemon.

    Raises:
        AuthError: The token is missing or wrong (checked before anything else).
        ProtocolError, PermissionModeError: See validate_request.
    """
    data = decode_line(line)
    if not tokens_match(data.get("token"), expected_token):
        raise AuthError("missing or wrong token")
    if set(data) - {"op", "args", "token"}:
        raise ProtocolError('a request has only "op", "args" and "token"')
    return validate_request(data.get("op"), data.get("args", {}))


def encode_ok(result: Any) -> bytes:
    """The reply line for a successful op."""
    return encode_line({"ok": True, "result": result})


def encode_error(error: str) -> bytes:
    """The reply line for a failed op."""
    return encode_line({"ok": False, "error": error})


def encode_line(payload: dict[str, Any]) -> bytes:
    """JSON-encode payload as one newline-terminated line within MAX_LINE_BYTES.

    Raises:
        ProtocolError: The encoded line is too long.
    """
    line = json.dumps(payload, ensure_ascii=False).encode(ENCODING) + LINE_END
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError(f"message is {len(line)} bytes; the limit is {MAX_LINE_BYTES}")
    return line


def decode_line(line: bytes) -> dict[str, Any]:
    """Decode one line into a JSON object, enforcing MAX_LINE_BYTES.

    Raises:
        ProtocolError: Too long, not UTF-8 JSON, or not an object.
    """
    if len(line) > MAX_LINE_BYTES:
        raise ProtocolError(f"line is longer than {MAX_LINE_BYTES} bytes")
    try:
        data = json.loads(line.decode(ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError(f"line is not UTF-8 JSON: {error}") from error
    if not isinstance(data, dict):
        raise ProtocolError("line must be a JSON object")
    return data


def _check_arg(op: str, spec: ArgSpec, args: dict[str, Any]) -> None:
    """Presence, type and size of one argument."""
    if spec.name not in args:
        if spec.is_required:
            raise ProtocolError(f"{op} needs {spec.name!r}")
        return
    value = args[spec.name]
    # bool is an int subclass; True is never a valid count.
    if not isinstance(value, spec.kind) or isinstance(value, bool):
        raise ProtocolError(f"{spec.name!r} must be a {spec.kind.__name__}")
    if isinstance(value, str):
        if spec.is_required and not value.strip():
            raise ProtocolError(f"{spec.name!r} must not be blank")
        if spec.max_chars is not None and len(value) > spec.max_chars:
            raise ProtocolError(f"{spec.name!r} is longer than {spec.max_chars} characters")


def _check_values(args: dict[str, Any]) -> None:
    """Rules on argument values that hold for every op using them."""
    for key in ("id", "session"):
        if key in args and not ID_PATTERN.fullmatch(args[key]):
            raise ProtocolError(f"{key!r} {args[key]!r} isn't a session id")
    if "last_n" in args and not 0 <= args["last_n"] <= MAX_STATUS_TEXTS:
        raise ProtocolError(f'"last_n" must be between 0 and {MAX_STATUS_TEXTS}')
    if "permission_mode" in args:
        validate_permission_mode(args["permission_mode"])
