"""The request guard: Host, Origin, session token and local key, as one security table."""

import pytest

from signal_console.open_hint import open_command
from signal_console.paths import TOOL_ROOT
from signal_console.server import SESSION_TOKEN_HEADER

OWN, EVIL = "own", "evil"


def _headers(console, host: str, origin: str | None, credential: str | None) -> dict[str, str]:
    port = console.client.port
    hosts = {
        OWN: f"127.0.0.1:{port}",
        "localhost": f"localhost:{port}",
        EVIL: f"evil.example:{port}",
        "other-port": f"127.0.0.1:{port + 1}",
    }
    headers = {"Host": hosts[host]}
    if origin is not None:
        headers["Origin"] = console.origin if origin == OWN else "http://evil.example"
    if credential == "token":
        headers[SESSION_TOKEN_HEADER] = console.token
    elif credential in ("key", "bad-key"):
        headers["X-Console-Key"] = console.services.local_key if credential == "key" else "nope"
    return headers


@pytest.mark.parametrize(
    ("method", "path", "host", "origin", "credential", "expected"),
    [
        ("GET", "/api/state", OWN, None, "token", 200),
        ("GET", "/api/state", "localhost", None, "token", 200),
        ("GET", "/api/state", OWN, None, None, 401),
        ("GET", "/api/state", EVIL, None, "token", 403),  # DNS rebinding
        ("GET", "/api/state", "other-port", None, "token", 403),
        ("GET", "/api/state", OWN, EVIL, "token", 403),
        ("POST", "/api/send", OWN, OWN, "token", 202),
        ("POST", "/api/send", OWN, None, "token", 403),  # a page POST must carry Origin
        ("POST", "/api/send", OWN, EVIL, "token", 403),
        # Buttons run in the server, so they sit behind the same login and Origin check.
        ("POST", "/api/action", OWN, OWN, None, 401),
        ("POST", "/api/action", OWN, EVIL, "token", 403),
        ("POST", "/api/login", OWN, None, None, 403),
        # Admitted: 400 only because {"text": "hi"} isn't a turn report.
        ("POST", "/api/hook/turn", OWN, None, "key", 400),
        ("POST", "/api/hook/turn", OWN, None, "bad-key", 403),
        ("POST", "/api/hook/turn", OWN, EVIL, "key", 403),
        # The camera proxy and the Away/Here toggle sit behind the same login.
        ("GET", "/api/camera/stream", OWN, None, None, 401),
        ("GET", "/api/devices", OWN, None, None, 401),
        ("POST", "/api/away", OWN, OWN, None, 401),
        ("POST", "/api/away", OWN, EVIL, "token", 403),
        ("GET", "/", OWN, None, None, 200),  # the page itself is public; its data isn't
    ],
)
async def test_guard_admits_only_own_page_and_local_callers(
    console, method, path, host, origin, credential, expected
):
    headers = _headers(console, host, origin, credential)
    response = await console.client.request(method, path, headers=headers, json={"text": "hi"})
    assert response.status == expected
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "Access-Control-Allow-Origin" not in response.headers


@pytest.mark.parametrize(
    ("path", "body", "reason"),
    [
        ("/api/state", None, "not signed in"),  # no token
        ("/api/login", {"key": "used-or-expired"}, "that login key is wrong, used or expired"),
    ],
)
async def test_signed_out_body_is_the_reason_and_open_command_only(console, path, body, reason):
    method = "GET" if body is None else "POST"
    headers = {} if body is None else {"Origin": console.origin}
    response = await console.client.request(method, path, headers=headers, json=body)
    assert response.status == 401
    assert await response.json() == {"error": reason, "openCommand": open_command()}
    # The absolute project path is quoted, so a folder with a space in it still runs.
    assert f'--project "{TOOL_ROOT}" ' in open_command()
    raw = await response.text()
    assert console.token not in raw and console.services.local_key not in raw
    assert "Set-Cookie" not in response.headers
    assert not any(name.startswith("Access-Control-") for name in response.headers)


@pytest.mark.parametrize(
    ("method", "path", "header", "expected"),
    [
        ("GET", "/api/state", b"X-Console-Token", 401),
        ("POST", "/api/hook/turn", b"X-Console-Key", 403),
    ],
)
async def test_credential_that_isnt_utf8_is_refused_not_a_crash(
    console, method, path, header, expected
):
    # Bytes that aren't UTF-8, in the credential and in a cookie, which nothing should parse.
    junk = b": \xff\xfe\xc3(\r\nCookie: console_session=\xff\xfe\r\n"
    status, _ = await console.raw_request(method, path, header + junk)
    assert status == expected
