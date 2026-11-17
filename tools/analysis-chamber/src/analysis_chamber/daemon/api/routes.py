"""dispatch: map an authenticated request's path and JSON body to a Chamber operation.

Field types are checked here (the trust boundary for request bodies); the
Chamber methods take typed arguments. A refused request raises ChamberError,
which the server turns into a 400 with the message.
"""

from typing import Any

from analysis_chamber.daemon.engine import Chamber, ChamberError


async def dispatch(chamber: Chamber, path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run the route for `path`.

    Args:
        chamber: The run registry.
        path: The request path.
        body: The JSON body.

    Returns:
        The JSON-ready reply.

    Raises:
        ChamberError: Unknown route, a bad field, or the operation was refused.
    """
    match path:
        case "/start":
            return await chamber.start(_text(body, "question"))
        case "/approve":
            edits = _optional(body, "edits", str)
            personal = _optional(body, "personal", bool)
            return await chamber.approve(_text(body, "run_id"), edits, personal)
        case "/status":
            return chamber.status(_text(body, "run_id"))
        case "/list":
            return chamber.list_runs()
        case "/ask":
            return await chamber.ask(_text(body, "run_id"), _text(body, "question"))
        case "/cancel":
            return await chamber.cancel(_text(body, "run_id"))
    raise ChamberError(f"no route {path}")


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ChamberError(f"{key} must be a non-empty string")
    return value


def _optional[T](body: dict[str, Any], key: str, kind: type[T]) -> T | None:
    value = body.get(key)
    if value is not None and not isinstance(value, kind):
        if kind is bool:
            raise ChamberError(f"set {key} yes/no (true or false)")
        raise ChamberError(f"{key} must be a {kind.__name__}")
    return value
