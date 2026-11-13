"""Draft MIME: build the RFC 2822 message Gmail's drafts.create wants, including reply headers.

Gmail only files a draft into a thread when it has the thread id, In-Reply-To
and References pointing at the original, and a matching subject. Gmail fills
in From itself.
"""

import base64
from dataclasses import dataclass, replace
from email.message import EmailMessage

from mail_tool.errors import MailError

REPLY_PREFIX = "Re: "


@dataclass(frozen=True)
class DraftContent:
    """What goes into a draft. in_reply_to/references are set only for replies."""

    to: str
    subject: str
    body: str
    in_reply_to: str = ""
    references: str = ""


def as_reply(content: DraftContent, original_headers: dict[str, str]) -> DraftContent:
    """Add reply headers taken from the original message.

    Args:
        content: The draft as the caller wrote it. An empty subject becomes "Re: <original>".
        original_headers: header_map() of the message being replied to.

    Returns:
        The draft with In-Reply-To, References and (if empty) the subject filled in.
    """
    message_id = original_headers.get("message-id", "").strip()
    earlier = original_headers.get("references", "").strip()
    references = f"{earlier} {message_id}".strip() if message_id else earlier
    subject = content.subject.strip() or _reply_subject(original_headers.get("subject", ""))
    return replace(content, subject=subject, in_reply_to=message_id, references=references)


def encode_draft(content: DraftContent) -> str:
    """The draft as a base64url RFC 2822 message (Gmail's `raw` field).

    Raises:
        MailError: A header (to, subject) contains a line break.
    """
    message = EmailMessage()
    try:
        message["To"] = content.to
        message["Subject"] = content.subject
        if content.in_reply_to:
            message["In-Reply-To"] = content.in_reply_to
        if content.references:
            message["References"] = content.references
    except ValueError:
        # The email package refuses CR/LF in headers, which would let text inject new headers.
        raise MailError("`to` and `subject` can't contain line breaks.") from None
    message.set_content(content.body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


def _reply_subject(original: str) -> str:
    """'Re: <original>' unless it already starts with Re:."""
    original = original.strip()
    return original if original.lower().startswith("re:") else REPLY_PREFIX + original
