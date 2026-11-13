"""extract_content: a Gmail message payload's readable body text and its attachment list.

Walks the MIME tree. The first text/plain part wins; with none, the first
text/html part is converted to text. Any part with a file name is listed as
an attachment (name, type, size) and never downloaded.
"""

import base64
import binascii
from dataclasses import dataclass, field
from email.message import Message
from typing import Any

from mail_tool.gmail.headers import header_map
from mail_tool.gmail.html_text import html_to_text

DEFAULT_CHARSET = "utf-8"
UNNAMED_ATTACHMENT = "(unnamed)"


@dataclass(frozen=True)
class Attachment:
    """One attachment's metadata (the bytes are never fetched)."""

    filename: str
    mime_type: str
    size: int


@dataclass(frozen=True)
class MessageContent:
    """A message's body as plain text, plus its attachments."""

    text: str
    attachments: list[Attachment]


@dataclass
class _Found:
    plain: list[str] = field(default_factory=list)
    html: list[str] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)


def extract_content(payload: dict[str, Any]) -> MessageContent:
    """Pick the body text and list attachments.

    Args:
        payload: message["payload"] from a format=full Gmail message or draft.

    Returns:
        The content; text is "" when the message has no text part.
    """
    found = _Found()
    _walk(payload, found)
    if found.plain:
        text = found.plain[0]
    elif found.html:
        text = html_to_text(found.html[0])
    else:
        text = ""
    return MessageContent(text=text.strip(), attachments=found.attachments)


def _walk(part: object, found: _Found) -> None:
    """Visit one MIME part and its children depth-first, in order."""
    if not isinstance(part, dict):
        return
    mime_type = str(part.get("mimeType", "")).lower()
    body = part.get("body") if isinstance(part.get("body"), dict) else {}
    if part.get("filename"):
        size = body.get("size", 0)
        found.attachments.append(
            Attachment(str(part["filename"]), mime_type, size if isinstance(size, int) else 0)
        )
        return
    # shortcut: a text part Gmail stored out of line (body.attachmentId, no data) reads as
    # empty; fetch it via messages.attachments.get if huge plain-text mail ever matters.
    if mime_type == "text/plain":
        found.plain.append(_decode_text(part, body))
    elif mime_type == "text/html":
        found.html.append(_decode_text(part, body))
    for child in part.get("parts") or []:
        _walk(child, found)


def _decode_text(part: dict[str, Any], body: dict[str, Any]) -> str:
    """Decode a text part's base64url data with its declared charset."""
    data = str(body.get("data", ""))
    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    except (binascii.Error, ValueError):
        return "[this part's data couldn't be decoded]"
    charset = _charset(part) or DEFAULT_CHARSET
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:  # an unknown charset name in the header
        return raw.decode(DEFAULT_CHARSET, errors="replace")


def _charset(part: dict[str, Any]) -> str | None:
    """The charset parameter of the part's Content-Type header, if any."""
    content_type = header_map(part).get("content-type")
    if not content_type:
        return None
    holder = Message()
    holder["Content-Type"] = content_type
    return holder.get_content_charset()
