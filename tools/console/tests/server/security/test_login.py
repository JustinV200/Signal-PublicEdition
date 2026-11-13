"""Page login: a one-time key from the local route buys a session token, never a cookie."""

from signal_console.server import SESSION_TOKEN_HEADER, SessionAuth
from signal_console.server.security import LOGIN_KEY_TTL_S, MAX_SESSIONS


async def test_login_key_buys_a_token_once_and_sets_no_cookie(console):
    client = console.client
    issued = await client.post(
        "/api/local/login-key", headers={"X-Console-Key": console.services.local_key}
    )
    key = (await issued.json())["key"]

    login = await client.post("/api/login", json={"key": key}, headers={"Origin": console.origin})
    assert login.status == 200
    assert "Set-Cookie" not in login.headers
    token = (await login.json())["token"]
    state = await client.get("/api/state", headers={SESSION_TOKEN_HEADER: token})
    assert state.status == 200

    reused = await client.post("/api/login", json={"key": key}, headers={"Origin": console.origin})
    assert reused.status == 401


def test_expired_login_key_is_refused():
    now = [0.0]
    auth = SessionAuth(clock=lambda: now[0])
    stale_key = auth.issue_login_key()
    now[0] += LOGIN_KEY_TTL_S + 1
    assert auth.log_in(stale_key) is None


def test_each_login_mints_a_new_token_and_the_oldest_drops_past_the_cap():
    auth = SessionAuth()
    tokens = [auth.log_in(auth.issue_login_key()) for _ in range(MAX_SESSIONS + 1)]

    assert len(set(tokens)) == len(tokens)
    assert not auth.is_session_token(tokens[0])
    assert all(auth.is_session_token(token) for token in tokens[1:])
