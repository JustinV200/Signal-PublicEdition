"""Read a request's JSON object body, answering 400 for anything else."""

import json
from typing import Any

from aiohttp import web


async def read_json_object(request: web.Request) -> dict[str, Any]:
    """The body as a JSON object.

    The bytes are parsed as JSON text (UTF-8) whatever charset the Content-Type
    names. request.json() would decode with that charset first, and a bogus
    one raises LookupError, which aiohttp answers with a 500.

    Raises:
        web.HTTPBadRequest: The body isn't JSON (or valid UTF-8), is nested too deep,
            or isn't an object.
        web.HTTPRequestEntityTooLarge: The body is over the app's size limit.
    """
    try:
        # A UnicodeDecodeError is a ValueError too. RecursionError: nested too deep to parse.
        body = json.loads(await request.read())
    except (ValueError, RecursionError) as error:
        raise bad_request(f"the body must be JSON ({error})") from error
    if not isinstance(body, dict):
        raise bad_request("the body must be a JSON object")
    return body


def bad_request(reason: str) -> web.HTTPBadRequest:
    """A 400 with a JSON {error} body, to raise."""
    return web.HTTPBadRequest(text=json.dumps({"error": reason}), content_type="application/json")
