"""MailService: the mail tool's operations - accounts, search, read, thread, draft, send.

Both the MCP tools and the CLI call these (send_to_self is CLI-only). Each takes
`account` as an alias or an email address. Results are plain dicts and lists
(JSON-ready), with every email-derived string wrapped by wrap_untrusted. Calls
block on the network, so async callers run them in a worker thread.
"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any

from mail_tool.auth import AccountRecord, TokenStore
from mail_tool.errors import GmailNotFound, MailError, OfflineError, ReauthRequired, SendRefused
from mail_tool.gmail import (
    DraftContent,
    GmailClient,
    HttpSession,
    as_reply,
    checked_id,
    encode_draft,
    header_map,
)
from mail_tool.service.recipients import normalized_to
from mail_tool.service.self_send import SELF_ADDRESS, self_message
from mail_tool.service.send_gate import SendGate
from mail_tool.service.views import message_view, received_ms, summary_view

# Opens an authorized HTTP session for an account (auth.GoogleSessions, or a fake).
SessionOpener = Callable[[AccountRecord], HttpSession]

DEFAULT_MAX_RESULTS = 20
MAX_RESULTS_LIMIT = 50
READ_BODY_CHARS = 20_000
THREAD_BODY_CHARS = 5_000
# Whole-thread body budget; the oldest messages are left out past it.
THREAD_TOTAL_CHARS = 30_000
# Parallel metadata GETs per search; under requests' default pool of 10 connections.
SEARCH_WORKERS = 8
SEARCH_HEADERS = ["From", "To", "Subject"]


class MailService:
    """The mail operations over the saved accounts."""

    def __init__(self, store: TokenStore, open_session: SessionOpener, send_gate: SendGate) -> None:
        """Args: store: saved accounts; open_session: HTTP per account; send_gate: send approval."""
        self._store = store
        self._open_session = open_session
        self._send_gate = send_gate

    def list_accounts(self) -> list[dict[str, str]]:
        """Every saved account with a live status: "ok", "needs re-auth", "offline" or "error".

        The status comes from one cheap users/me/profile call, not retried. Offline, the email
        shown is the one saved at sign-in.
        """
        return [self._account_status(alias) for alias in self._store.aliases()]

    def search(
        self, account: str, query: str, max_results: int = DEFAULT_MAX_RESULTS
    ) -> list[dict[str, Any]]:
        """Messages matching a Gmail search query, newest first (summary view).

        Args:
            account: Alias or address.
            query: Gmail search syntax, e.g. "is:unread newer_than:1d".
            max_results: 1-50 (clamped).

        Raises:
            MailError: Unknown account, re-auth needed, offline, or a Gmail error.
        """
        client = self._client_for(account)
        limit = min(max(1, max_results), MAX_RESULTS_LIMIT)
        listing = client.get("messages", {"q": query, "maxResults": limit})
        params = {"format": "metadata", "metadataHeaders": SEARCH_HEADERS}
        hits = [item for item in listing.get("messages") or [] if isinstance(item, dict)]
        ids = [checked_id(str(hit.get("id")), "message") for hit in hits]

        def fetch(message_id: str) -> dict[str, Any] | None:
            try:
                return client.get(f"messages/{message_id}", params)
            except GmailNotFound:
                return None  # deleted between the listing and this GET

        # The listing call above already refreshed the token, so the workers share it.
        with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as pool:
            messages = list(pool.map(fetch, ids))  # map keeps the newest-first order
        return [summary_view(message) for message in messages if message is not None]

    def read(self, account: str, message_id: str) -> dict[str, Any]:
        """One message: headers, plain-text body (capped) and attachment list.

        Raises:
            MailError: As search(), or an invalid id.
        """
        client = self._client_for(account)
        message = client.get(f"messages/{checked_id(message_id, 'message')}", {"format": "full"})
        return message_view(message, READ_BODY_CHARS)

    def thread(self, account: str, thread_id: str) -> dict[str, Any]:
        """A whole conversation, oldest message first.

        Each body has quoted earlier mail removed and is capped. If the bodies
        still pass THREAD_TOTAL_CHARS, the oldest messages are left out and
        "messages_omitted" says how many.

        Raises:
            MailError: As read().
        """
        client = self._client_for(account)
        data = client.get(f"threads/{checked_id(thread_id, 'thread')}", {"format": "full"})
        messages = sorted(data.get("messages") or [], key=received_ms)
        views = [message_view(message, THREAD_BODY_CHARS, True) for message in messages]
        total_chars = sum(len(view["body"]) for view in views)
        omitted = 0
        while total_chars > THREAD_TOTAL_CHARS and len(views) - omitted > 1:
            total_chars -= len(views[omitted]["body"])
            omitted += 1
        result: dict[str, Any] = {"thread_id": thread_id, "messages": views[omitted:]}
        if omitted:
            result["messages_omitted"] = omitted
        return result

    def create_draft(
        self, account: str, content: DraftContent, reply_to_message_id: str | None = None
    ) -> dict[str, Any]:
        """Save a draft (never sends). A reply joins the original's thread.

        Args:
            account: Alias or address.
            content: To, subject and body. Replying with an empty subject uses "Re: <original>".
            reply_to_message_id: The message being answered, if any.

        Returns:
            {"draft_id", "message_id", "thread_id"}.

        Raises:
            MailError: No recipient, a `to` that send couldn't parse, line breaks in
                headers, or as read().
        """
        if not content.to.strip():
            raise MailError("A draft needs at least one recipient in `to`.")
        # Checked as send checks it, so every saved draft can be sent.
        content = replace(content, to=normalized_to(content.to))
        client = self._client_for(account)
        message: dict[str, Any] = {}
        if reply_to_message_id:
            path = f"messages/{checked_id(reply_to_message_id, 'message')}"
            original = client.get(path, {"format": "metadata"})
            content = as_reply(content, header_map(original.get("payload") or {}))
            message["threadId"] = original.get("threadId")
        message["raw"] = encode_draft(content)
        draft = client.post("drafts", {"message": message})
        sent_message = draft.get("message") or {}
        return {
            "draft_id": draft.get("id"),
            "message_id": sent_message.get("id"),
            "thread_id": sent_message.get("threadId"),
        }

    def send_draft(self, account: str, draft_id: str) -> dict[str, Any]:
        """Send a saved draft, after the owner approves it (config send.confirm).

        Raises:
            SendRefused: Unreadable or too many recipients, the owner denied or didn't
                answer, or the draft changed while the dialog was open; nothing was sent.
            MailError: As read().
        """
        record = self._store.find(account)
        client = self._client(record)
        draft_id = checked_id(draft_id, "draft")
        draft = client.get(f"drafts/{draft_id}", {"format": "full"})
        approved_message_id = (draft.get("message") or {}).get("id")
        self._send_gate.check(record, draft.get("message") or {})
        # Gmail gives a draft a new message id on every edit. Only send the version
        # the owner saw: the dialog can stay open for minutes.
        current = client.get(f"drafts/{draft_id}", {"format": "minimal"})
        if (
            not approved_message_id
            or (current.get("message") or {}).get("id") != approved_message_id
        ):
            raise SendRefused(
                "The draft changed while the owner was deciding, so it was not sent. "
                "Send it again to show the owner the new version."
            )
        sent = client.post("drafts/send", {"id": draft_id})
        return {"sent": True, "message_id": sent.get("id"), "thread_id": sent.get("threadId")}

    def send_to_self(self, subject: str, body: str) -> dict[str, Any]:
        """Send a plain-text email from SELF_ADDRESS's account to SELF_ADDRESS, with no dialog.

        See self_send.py for why this one send skips the owner's Allow dialog.

        Returns:
            {"sent": True, "to": SELF_ADDRESS, "message_id"}.

        Raises:
            MailError: The subject or body breaks self_message's rules (checked
                before any network call), no saved account is SELF_ADDRESS, or as read().
        """
        raw = self_message(subject, body)
        client = self._client(self._store.find(SELF_ADDRESS))
        sent = client.post("messages/send", {"raw": raw})
        return {"sent": True, "to": SELF_ADDRESS, "message_id": sent.get("id")}

    def _account_status(self, alias: str) -> dict[str, str]:
        """One list_accounts row."""
        try:
            record = self._store.load(alias)
        except ReauthRequired as error:
            return {"alias": alias, "email": "", "status": "needs re-auth", "detail": str(error)}
        row = {"alias": alias, "email": record.email}
        try:
            self._client(record).get("profile", retry=False)
        except ReauthRequired as error:
            return row | {"status": "needs re-auth", "detail": str(error)}
        except OfflineError as error:
            return row | {"status": "offline", "detail": f"{error} Email is from the sign-in."}
        except MailError as error:
            return row | {"status": "error", "detail": str(error)}
        return row | {"status": "ok"}

    def _client_for(self, account: str) -> GmailClient:
        return self._client(self._store.find(account))

    def _client(self, record: AccountRecord) -> GmailClient:
        return GmailClient(self._open_session(record), record.alias)
