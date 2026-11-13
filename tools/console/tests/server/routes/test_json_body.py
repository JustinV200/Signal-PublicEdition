"""JSON bodies are read as UTF-8 whatever charset the request names, and a body that
can't be parsed (even one nested too deep for the parser) is a 400, never a 500."""

import json

import pytest

# Deeper than Python's recursion limit, still well under the body size limit.
TOO_DEEP = b"[" * 5000 + b"]" * 5000


@pytest.mark.parametrize(
    ("charset", "body", "status"),
    [
        ("bogus", None, 200),  # None: a valid login body
        ("utf-8", TOO_DEEP, 400),
    ],
    ids=["bogus-charset", "too-deep"],
)
async def test_a_body_is_parsed_as_utf8_json_and_bad_ones_are_400(console, charset, body, status):
    key = console.services.auth.issue_login_key()
    headers = {"Origin": console.origin, "Content-Type": f"application/json; charset={charset}"}
    data = body if body is not None else json.dumps({"key": key}).encode()

    login = await console.client.post("/api/login", data=data, headers=headers)

    assert login.status == status
