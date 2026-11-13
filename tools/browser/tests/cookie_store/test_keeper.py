"""CookieKeeper with a fake browser context: the save/restore round trip and corrupt files.

Real DPAPI (the test runs as the owner); the file lives in tmp_path.
"""

import json
import logging
import subprocess

import pytest

from browser_tool.cookie_store import DPAPI_ENTROPY, CookieKeeper, CookieMode, secret_file
from browser_tool.cookie_store.dpapi import protect
from browser_tool.policy import HostPolicy

NOW = 1_800_000_000.0
SECRET = "s3cret-cookie-value"
# The loading browser's policy: a checker-style allowlist.
POLICY = HostPolicy.from_strings(["classroom.google.com", "*.duosecurity.com"], [])


def _cookie(name: str, domain: str, expires: float = -1, **extra) -> dict:
    """A cookie as BrowserContext.cookies() reports it."""
    return {
        "name": name,
        "value": SECRET,
        "domain": domain,
        "path": "/",
        "expires": expires,
        "httpOnly": True,
        "secure": True,
        "sameSite": "Lax",
        **extra,
    }


SAVED = [
    _cookie("session_exact", "classroom.google.com"),
    _cookie("persistent_parent", ".google.com", NOW + 3600),
    _cookie("persistent_under_wildcard", ".duosecurity.com", NOW + 3600),
    _cookie("expired", ".google.com", NOW - 1),
    _cookie("other_host", ".example.com", NOW + 3600),
    _cookie("session_other_google_host", "mail.google.com"),
    _cookie("partitioned", "classroom.google.com", partitionKey="https://x.com"),
]


class FakeContext:
    """The two BrowserContext calls CookieKeeper makes."""

    def __init__(self, cookies: list[dict] | None = None):
        self._cookies = cookies or []
        self.added: list[dict] = []

    async def cookies(self) -> list[dict]:
        return self._cookies

    async def add_cookies(self, cookies: list[dict]) -> None:
        self.added.extend(cookies)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        # The checker: every unexpired cookie its own allowlist would be sent.
        (CookieMode.BORROW, {"session_exact", "persistent_parent", "persistent_under_wildcard"}),
        # The desktop: its profile keeps persistent cookies, so only session ones come back.
        (CookieMode.OWN, {"session_exact"}),
    ],
    ids=["borrow", "own"],
)
async def test_saved_cookies_come_back_unexpired_and_only_for_allowed_hosts(
    tmp_path, mode, expected
):
    path = tmp_path / ".state" / "cookies.bin"
    await CookieKeeper(path, POLICY, CookieMode.OWN, clock=lambda: NOW).save(FakeContext(SAVED))
    assert SECRET.encode() not in path.read_bytes()  # encrypted at rest

    browser = FakeContext()
    await CookieKeeper(path, POLICY, mode, clock=lambda: NOW).restore(browser)

    assert {cookie["name"] for cookie in browser.added} == expected
    assert all("partitionKey" not in cookie for cookie in browser.added)


@pytest.mark.asyncio
async def test_borrowing_never_writes_the_file(tmp_path):
    path = tmp_path / "cookies.bin"
    await CookieKeeper(path, POLICY, CookieMode.BORROW).save(FakeContext(SAVED))
    assert not path.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "blob",
    [
        b"not a dpapi blob",
        protect(b"{not json", DPAPI_ENTROPY),
        protect(json.dumps({"version": 1, "cookies": [{"name": SECRET}]}).encode(), DPAPI_ENTROPY),
        # A blob of this user made for something else (other entropy).
        protect(json.dumps({"version": 1, "cookies": SAVED}).encode(), b"other-use"),
    ],
    ids=["garbage", "not-json", "bad-shape", "wrong-entropy"],
)
async def test_an_unusable_file_is_ignored_with_a_log_line_by_type_only(tmp_path, caplog, blob):
    path = tmp_path / "cookies.bin"
    path.write_bytes(blob)
    browser = FakeContext()

    with caplog.at_level(logging.INFO):
        await CookieKeeper(path, POLICY, CookieMode.BORROW).restore(browser)

    assert browser.added == []
    assert "ignoring the saved cookies file" in caplog.text
    assert SECRET not in caplog.text


def _refusing_icacls(command, **_kwargs):
    """icacls that runs and refuses (non-zero exit)."""
    return subprocess.CompletedProcess(command, 5, stdout="", stderr="Access is denied.")


@pytest.mark.asyncio
@pytest.mark.parametrize("is_missing", [True, False], ids=["missing-command", "non-zero-exit"])
async def test_a_failed_owner_only_acl_saves_nothing(tmp_path, monkeypatch, caplog, is_missing):
    if is_missing:
        monkeypatch.setattr(secret_file, "ICACLS", "no-such-icacls-command")
    else:
        monkeypatch.setattr(secret_file.subprocess, "run", _refusing_icacls)
    path = tmp_path / "cookies.bin"
    path.write_bytes(b"previous save")

    with caplog.at_level(logging.WARNING):
        await CookieKeeper(path, POLICY, CookieMode.OWN).save(FakeContext(SAVED))

    assert "cookies weren't saved" in caplog.text
    assert path.read_bytes() == b"previous save"
    assert list(tmp_path.glob(".cookies.*.tmp")) == []
