"""Tests for PhoneServer's security boundary: the token link, the session cookie, Host and Origin.

A real server on a free loopback port and a real aiohttp client, so the
cookie attributes, handshake refusals and close codes are the ones a phone
browser would see.
"""

import contextlib

import aiohttp
import pytest

from audiohub.config import PhoneSettings
from audiohub.phone import (
    COOKIE_NAME,
    REPLACED_CLOSE_CODE,
    PhoneLink,
    PhoneServer,
    session_cookie_value,
)

TAILNET_HOST = "pc.tail1234.ts.net"
USE_TOKEN = object()  # stands for "the running server's raw token" in parametrize


@contextlib.asynccontextmanager
async def running_phone(tmp_path):
    settings = PhoneSettings(port=0, allowed_hosts=(TAILNET_HOST,))
    server = PhoneServer(PhoneLink(), settings, token_path=tmp_path / "phone-token")
    async with server, aiohttp.ClientSession() as http:
        yield server, http


def _base(server) -> str:
    return f"http://127.0.0.1:{server.port}"


def _headers(server, cookie=None, origin=None, host=None) -> dict[str, str]:
    """Browser-like headers: the valid cookie and local Origin unless told otherwise."""
    cookie = session_cookie_value(server.token) if cookie is None else cookie
    cookie = server.token if cookie is USE_TOKEN else cookie
    origin = _base(server) if origin is None else origin
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"} if cookie else {}
    if origin:
        headers["Origin"] = origin
    if host:
        headers["Host"] = host
    return headers


@pytest.mark.asyncio
async def test_token_link_sets_a_strict_session_cookie_then_redirects(tmp_path):
    async with running_phone(tmp_path) as (server, http):
        assert (tmp_path / "phone-token").read_text() == server.token
        response = await http.get(f"{_base(server)}/?token={server.token}")
        assert response.status == 200
        assert 'http-equiv="refresh" content="0;url=/"' in await response.text()
        cookie = response.cookies[COOKIE_NAME]
        assert cookie.value == session_cookie_value(server.token) != server.token
        assert cookie["httponly"] and cookie["secure"] and cookie["samesite"] == "Strict"
        page = await http.get(f"{_base(server)}/", headers=_headers(server))
        assert page.status == 200
        assert "<title>audiohub phone</title>" in await page.text()
    assert not (tmp_path / "phone-token").exists()


@pytest.mark.parametrize("path", ["/?token=wrong", "/", "/app.js"])
@pytest.mark.asyncio
async def test_page_needs_the_token_or_the_cookie(tmp_path, path):
    async with running_phone(tmp_path) as (server, http):
        response = await http.get(f"{_base(server)}{path}")
        assert response.status == 403
        assert response.headers.get("Connection", "").lower() == "close"


@pytest.mark.parametrize(
    "overrides",
    [
        {"cookie": ""},
        {"cookie": "0" * 64},
        {"cookie": USE_TOKEN},  # the cookie is an HMAC, never the token itself
        {"origin": ""},
        {"origin": "https://evil.example"},
        {"origin": f"http://{TAILNET_HOST}"},  # the tailnet is reached over HTTPS only
        {"origin": "http://127.0.0.1:1"},  # another local app; cookies ignore ports
        {"host": "evil.example"},  # DNS rebinding
    ],
    ids=[
        "no-cookie",
        "wrong-cookie",
        "raw-token",
        "no-origin",
        "foreign-origin",
        "http",
        "other-local-port",
        "host",
    ],
)
@pytest.mark.asyncio
async def test_socket_is_refused_without_the_cookie_or_from_elsewhere(tmp_path, overrides):
    async with running_phone(tmp_path) as (server, http):
        with pytest.raises(aiohttp.WSServerHandshakeError) as refusal:
            await http.ws_connect(f"{_base(server)}/ws", headers=_headers(server, **overrides))
        assert refusal.value.status == 403


@pytest.mark.parametrize("host", [None, TAILNET_HOST])
@pytest.mark.asyncio
async def test_socket_opens_locally_and_through_tailscale(tmp_path, host):
    async with running_phone(tmp_path) as (server, http):
        origin = f"https://{host}" if host else None
        headers = _headers(server, origin=origin, host=host)
        async with http.ws_connect(f"{_base(server)}/ws", headers=headers) as socket:
            assert await socket.receive_json(timeout=1) == {"type": "mic", "on": True}


@pytest.mark.parametrize(
    "send",
    [
        lambda socket: socket.send_str("hello"),
        lambda socket: socket.send_str('{"type": "played", "id": true}'),
        lambda socket: socket.send_bytes(b"\x00"),  # half an int16 sample
        lambda socket: socket.send_bytes(b"\x00" * (64 * 1024)),  # over the size cap
    ],
    ids=["not-json", "bad-ack", "odd-bytes", "oversized"],
)
@pytest.mark.asyncio
async def test_first_bad_message_closes_the_socket(tmp_path, send):
    async with (
        running_phone(tmp_path) as (server, http),
        http.ws_connect(f"{_base(server)}/ws", headers=_headers(server)) as socket,
    ):
        await socket.receive_json(timeout=1)
        await send(socket)
        message = await socket.receive(timeout=1)
        assert message.type == aiohttp.WSMsgType.CLOSE
        assert socket.close_code in (1008, 1009)  # policy violation, or too big


@pytest.mark.asyncio
async def test_a_newer_phone_replaces_the_older_one(tmp_path):
    async with running_phone(tmp_path) as (server, http):
        url, headers = f"{_base(server)}/ws", _headers(server)
        async with http.ws_connect(url, headers=headers) as older:
            await older.receive_json(timeout=1)
            async with http.ws_connect(url, headers=headers) as newer:
                assert (await older.receive(timeout=1)).type == aiohttp.WSMsgType.CLOSE
                assert older.close_code == REPLACED_CLOSE_CODE
                assert await newer.receive_json(timeout=1) == {"type": "mic", "on": True}
