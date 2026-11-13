"""draft_recipients: every To/Cc/Bcc address of a draft as Gmail stores it, for the send dialog.

normalized_to applies the same parsing when a draft is made, so a draft that
gets saved can also be sent.

The dialog lists each bare address on its own line, so a long display name
or a crowd of other recipients can't hide one. Every copy of a repeated
header is read. Anything the parser can't turn into an address counts as a
refusal, because Gmail might still deliver to whatever is hidden there.
"""

from dataclasses import dataclass
from email.utils import formataddr, getaddresses
from typing import Any

from mail_tool.errors import MailError, SendRefused
from mail_tool.gmail import header_values

RECIPIENT_HEADERS = ("To", "Cc", "Bcc")
MAX_RECIPIENTS = 20
# RFC 5321's limit on a mailbox path; anything longer can't be a real address.
MAX_ADDRESS_CHARS = 254


@dataclass(frozen=True)
class Recipient:
    """One recipient: which header it's in ("To", "Cc", "Bcc") and its bare address."""

    kind: str
    address: str


def is_readable_address(address: str) -> bool:
    """True if the parser got a real-looking address: it has an '@' and isn't too long."""
    return "@" in address and len(address) <= MAX_ADDRESS_CHARS


def normalized_to(to: str) -> str:
    """A draft's `to` rewritten as a clean comma-separated header, checked as send checks it.

    Raises:
        MailError: Any part isn't a readable address (a trailing comma, ';' separators,
            a bare name...), there is none, or an address isn't ASCII.
    """
    pairs = getaddresses([to])
    if not all(is_readable_address(address) for _name, address in pairs):
        raise MailError(
            "`to` must be email addresses separated by commas, e.g. "
            "'alice@example.com, Bob <bob@example.com>'."
        )
    try:
        return ", ".join(formataddr(pair) for pair in pairs)
    except UnicodeEncodeError:
        raise MailError("`to` addresses must be plain ASCII (no accents before the '@').") from None


def draft_recipients(payload: dict[str, Any]) -> list[Recipient]:
    """Parse all recipients of a format=full draft payload.

    Args:
        payload: draft["message"]["payload"] from Gmail.

    Returns:
        The recipients in header order (To, then Cc, then Bcc).

    Raises:
        SendRefused: An address can't be parsed or is too long, or there are
            more than MAX_RECIPIENTS.
    """
    recipients = []
    for kind in RECIPIENT_HEADERS:
        values = [value for value in header_values(payload, kind) if value.strip()]
        # Strict parsing (Python 3.12.6+) returns ('', '') for a header it can't read.
        for _display_name, address in getaddresses(values):
            if not is_readable_address(address):
                raise SendRefused(
                    f"A {kind} address in this draft can't be read safely, so it was not "
                    "sent. Fix the draft's recipients and try again."
                )
            recipients.append(Recipient(kind, address))
    if len(recipients) > MAX_RECIPIENTS:
        raise SendRefused(
            f"This draft has {len(recipients)} recipients. Claude can send to at most "
            f"{MAX_RECIPIENTS} at once, so it was not sent; the owner can send it from Gmail."
        )
    return recipients
