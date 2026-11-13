"""Message views: Gmail message JSON -> the dicts the tools return, with email text wrapped.

Ids, labels and Gmail's own receive time are trusted. Everything that came
from the email (headers, snippet, body, attachment names) is wrapped by
wrap_untrusted, except attachment MIME types, which are checked against a strict
type/subtype pattern instead.
"""

import html
import re
from datetime import datetime
from typing import Any

from mail_tool.gmail import extract_content, header_map, strip_quoted
from mail_tool.service.untrusted import wrap_untrusted

MS_PER_SECOND = 1000
ADDRESS_HEADERS = ("from", "to")
TRUNCATION_NOTE = "\n[... truncated]"
# The sender writes Content-Type, so only a plain type/subtype is passed through unwrapped.
_MIME_TYPE_PATTERN = re.compile(r"[a-z0-9.+-]{1,64}/[a-z0-9.+-]{1,64}")
FALLBACK_MIME_TYPE = "application/octet-stream"


def summary_view(message: dict[str, Any]) -> dict[str, Any]:
    """The search-result view: ids, sender, recipients, subject, date, snippet, labels.

    Args:
        message: A Gmail message from format=metadata or format=full.
    """
    headers = header_map(_payload(message))
    view: dict[str, Any] = {"id": message.get("id"), "thread_id": message.get("threadId")}
    for name in ADDRESS_HEADERS:
        view[name] = wrap_untrusted(headers.get(name, ""))
    view["subject"] = wrap_untrusted(headers.get("subject", ""))
    view["date"] = _received_at(message)
    # Gmail HTML-escapes snippets (&#39; and so on).
    view["snippet"] = wrap_untrusted(html.unescape(str(message.get("snippet", ""))))
    view["labels"] = [str(label) for label in message.get("labelIds") or []]
    return view


def message_view(
    message: dict[str, Any], max_body_chars: int, is_quote_stripped: bool = False
) -> dict[str, Any]:
    """The full view: summary fields (minus snippet), Cc, plain-text body and attachments.

    Args:
        message: A Gmail message from format=full.
        max_body_chars: The body is cut to this many characters.
        is_quote_stripped: Drop quoted earlier mail from the body (strip_quoted).
    """
    view = summary_view(message)
    del view["snippet"]
    payload = _payload(message)
    cc = header_map(payload).get("cc", "")
    if cc:
        view["cc"] = wrap_untrusted(cc)
    content = extract_content(payload)
    text = strip_quoted(content.text) if is_quote_stripped else content.text
    is_truncated = len(text) > max_body_chars
    body = text[:max_body_chars] + (TRUNCATION_NOTE if is_truncated else "")
    view["body"] = wrap_untrusted(body)
    view["body_truncated"] = is_truncated
    view["attachments"] = [
        {
            "filename": wrap_untrusted(item.filename),
            "mime_type": _safe_mime_type(item.mime_type),
            "size": item.size,
        }
        for item in content.attachments
    ]
    return view


def received_ms(message: dict[str, Any]) -> int:
    """Gmail's internalDate (ms since the epoch), or 0 if missing or malformed."""
    try:
        return int(message.get("internalDate", 0))
    except (TypeError, ValueError):
        return 0


def _received_at(message: dict[str, Any]) -> str:
    """When Gmail received the message, in local time; trusted, unlike the Date header."""
    milliseconds = received_ms(message)
    if not milliseconds:
        return ""
    try:
        moment = datetime.fromtimestamp(milliseconds / MS_PER_SECOND).astimezone()
    except (OverflowError, OSError, ValueError):  # out of the platform's range (Windows: pre-1970)
        return ""
    return moment.isoformat(timespec="minutes")


def _safe_mime_type(mime_type: str) -> str:
    """The MIME type if it is a plain type/subtype, else application/octet-stream."""
    lowered = mime_type.lower()
    return lowered if _MIME_TYPE_PATTERN.fullmatch(lowered) else FALLBACK_MIME_TYPE


def _payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload")
    return payload if isinstance(payload, dict) else {}
