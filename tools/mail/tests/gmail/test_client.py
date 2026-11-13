"""Tests for GmailClient's error mapping: re-auth, offline, Gmail errors, and id checks."""

import pytest
import requests
from google.auth.exceptions import RefreshError
from support.fakes import SECRET_CLIENT_SECRET, SECRET_REFRESH_TOKEN, FakeResponse, FakeSession

from mail_tool.errors import GmailError, OfflineError, ReauthRequired
from mail_tool.gmail import GmailClient, checked_id


def test_invalid_grant_asks_for_mail_add_and_drops_the_library_error() -> None:
    # A worst case: the library error text mentions the secrets. None of it may surface.
    error = RefreshError(
        f"invalid_grant: Token has been expired or revoked. {SECRET_REFRESH_TOKEN}",
        {"error": "invalid_grant", "client_secret": SECRET_CLIENT_SECRET},
    )
    client = GmailClient(FakeSession({("GET", "profile"): error}), "personal")

    with pytest.raises(ReauthRequired) as caught:
        client.get("profile")

    message = str(caught.value)
    assert "re-run `mail add personal`" in message
    assert SECRET_REFRESH_TOKEN not in message and SECRET_CLIENT_SECRET not in message
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_network_failure_is_offline_and_gmail_errors_carry_their_message() -> None:
    session = FakeSession({("GET", "profile"): requests.ConnectionError("dns")})
    client = GmailClient(session, "personal")

    with pytest.raises(OfflineError):
        client.get("profile")
    with pytest.raises(GmailError, match="404: Requested entity was not found"):
        client.get("messages/abc")


def test_ids_that_could_change_the_url_path_are_refused() -> None:
    assert checked_id("18c2f0a9b7d1e3f4", "message") == "18c2f0a9b7d1e3f4"
    assert checked_id("r-1234567890", "draft") == "r-1234567890"
    for bad in ("../settings", "abc/def", "abc?x=1", ""):
        with pytest.raises(GmailError):
            checked_id(bad, "message")


def test_get_retries_a_transient_error_but_post_does_not() -> None:
    session = FakeSession(
        {
            ("GET", "profile"): [FakeResponse(503, None), {"emailAddress": "a@b.com"}],
            ("POST", "drafts/send"): FakeResponse(503, None),
        }
    )
    client = GmailClient(session, "personal")

    assert client.get("profile") == {"emailAddress": "a@b.com"}
    with pytest.raises(GmailError, match="503"):
        client.post("drafts/send", {"id": "r-1"})
    assert len(session.posted("drafts/send")) == 1
