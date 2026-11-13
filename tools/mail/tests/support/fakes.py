"""Shared test fakes: a Gmail HTTP session with canned routes, an in-memory store, builders.

No test talks to Google. FakeSession stands in for AuthorizedSession, and
FakeStore stands in for the DPAPI TokenStore (which has its own test).
"""

import base64
from collections.abc import Callable
from typing import Any

from mail_tool.auth import AccountRecord
from mail_tool.errors import AccountError
from mail_tool.gmail import API_BASE
from mail_tool.service import MailService, SendGate

# Planted secrets: tests assert these never show up in any output or error.
SECRET_REFRESH_TOKEN = "1//REFRESH-TOKEN-must-never-leak"
SECRET_CLIENT_SECRET = "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k"

PERSONAL = AccountRecord("personal", "owner@example.com", SECRET_REFRESH_TOKEN)
# The account whose address is the self-only send's SELF_ADDRESS.
ALT = AccountRecord("alt", "owner.alt@example.com", SECRET_REFRESH_TOKEN)
SAMPLE_HEADERS = {
    "From": "Alice <alice@example.com>",
    "To": "owner@example.com",
    "Subject": "Hi",
}


class FakeResponse:
    """A requests.Response stand-in."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class FakeSession:
    """Serves (method, path below users/me/) -> JSON dict, FakeResponse, or an exception to raise.

    A list serves its items one call at a time, then repeats the last. Unknown
    routes answer 404 the way Gmail does. Every call is recorded.
    """

    def __init__(self, routes: dict[tuple[str, str], Any] | None = None) -> None:
        self.routes = routes or {}
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        path = url.removeprefix(API_BASE)
        self.calls.append((method, path, kwargs))
        outcome = self.routes.get((method, path))
        if isinstance(outcome, list):
            outcome = outcome.pop(0) if len(outcome) > 1 else outcome[0]
        if outcome is None:
            return FakeResponse(404, {"error": {"message": "Requested entity was not found."}})
        if isinstance(outcome, Exception):
            raise outcome
        return outcome if isinstance(outcome, FakeResponse) else FakeResponse(200, outcome)

    def posted(self, path: str) -> list[dict[str, Any]]:
        """The JSON bodies POSTed to `path`."""
        return [kw["json"] for method, p, kw in self.calls if method == "POST" and p == path]


class FakeStore:
    """In-memory TokenStore: aliases, load, find."""

    def __init__(self, *records: AccountRecord) -> None:
        self.records = {record.alias: record for record in records}

    def aliases(self) -> list[str]:
        return sorted(self.records)

    def load(self, alias: str) -> AccountRecord:
        if alias not in self.records:
            raise AccountError(f"No mail account {alias!r}.")
        return self.records[alias]

    def find(self, account: str) -> AccountRecord:
        for record in self.records.values():
            if account.lower() in (record.alias, record.email.lower()):
                return record
        raise AccountError(f"No mail account {account!r}.")


class FakeOwner:
    """Records dialog requests and answers with `answer`."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.asked: list[tuple[str, str]] = []

    def __call__(self, title: str, message: str, *, timeout_s: float) -> bool:
        self.asked.append((title, message))
        return self.answer


def make_service(
    session: FakeSession, owner: Callable[..., bool] | None = None, *records: AccountRecord
) -> MailService:
    """A MailService over FakeStore(records or PERSONAL), `session` and a fake dialog."""
    store = FakeStore(*(records or (PERSONAL,)))
    gate = SendGate(is_enabled=True, ask=owner or FakeOwner(False))
    return MailService(store, lambda _record: session, gate)


def b64(text: str, charset: str = "utf-8") -> str:
    """Gmail's base64url body encoding."""
    return base64.urlsafe_b64encode(text.encode(charset)).decode("ascii")


def text_part(mime_type: str, text: str, charset: str = "utf-8") -> dict[str, Any]:
    """A text/plain or text/html MIME part."""
    content_type = f'{mime_type}; charset="{charset}"'
    return {
        "mimeType": mime_type,
        "filename": "",
        "headers": [{"name": "Content-Type", "value": content_type}],
        "body": {"size": len(text), "data": b64(text, charset)},
    }


def attachment_part(filename: str, mime_type: str, size: int) -> dict[str, Any]:
    """An attachment part (no data, like Gmail's format=full)."""
    return {
        "mimeType": mime_type,
        "filename": filename,
        "body": {"size": size, "attachmentId": "ANGjdJ-att"},
    }


def gmail_message(message_id: str, headers: dict[str, str], **fields: Any) -> dict[str, Any]:
    """A Gmail message; `parts` (list) go under a multipart/mixed payload, other fields as-is."""
    payload: dict[str, Any] = {
        "mimeType": "multipart/mixed",
        "headers": [{"name": name, "value": value} for name, value in headers.items()],
        "parts": fields.pop("parts", []),
    }
    message = {"id": message_id, "threadId": "t1", "labelIds": ["INBOX"], "payload": payload}
    message.update(fields)
    return message
