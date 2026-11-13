"""Public API of mail_tool.gmail: the Gmail REST client and message parsing helpers.

Nothing here knows about accounts on disk or untrusted-content wrapping; the
service package combines this with auth.
"""

from mail_tool.gmail.body import Attachment, MessageContent, extract_content
from mail_tool.gmail.client import API_BASE, GmailClient, HttpSession, checked_id
from mail_tool.gmail.drafts import DraftContent, as_reply, encode_draft
from mail_tool.gmail.headers import header_map, header_values
from mail_tool.gmail.html_text import html_to_text
from mail_tool.gmail.quotes import strip_quoted

__all__ = [
    "API_BASE",
    "Attachment",
    "DraftContent",
    "GmailClient",
    "HttpSession",
    "MessageContent",
    "as_reply",
    "checked_id",
    "encode_draft",
    "extract_content",
    "header_map",
    "header_values",
    "html_to_text",
    "strip_quoted",
]
