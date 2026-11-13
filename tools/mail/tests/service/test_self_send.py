"""Tests for the self-only send's text rules: caps and control characters, checked before Gmail."""

import base64
import email
from email import policy

import pytest
from support.fakes import ALT, FakeSession, make_service

from mail_tool.errors import MailError
from mail_tool.service.self_send import MAX_BODY_CHARS, MAX_SUBJECT_CHARS


@pytest.mark.parametrize(
    ("subject", "body"),
    [
        ("s" * (MAX_SUBJECT_CHARS + 1), "hi"),
        ("Signal digest", "x" * (MAX_BODY_CHARS + 1)),
        ("Signal digest", "hi\x1b[2Jthere"),
        ("Signal digest", "a lone\rcarriage return"),
    ],
    ids=["long subject", "long body", "escape in body", "carriage return in body"],
)
def test_bad_text_is_refused_before_any_gmail_call(subject: str, body: str) -> None:
    session = FakeSession()
    with pytest.raises(MailError):
        make_service(session, None, ALT).send_to_self(subject, body)
    assert session.calls == []


def test_line_breaks_tabs_and_accents_are_sent_unchanged() -> None:
    session = FakeSession({("POST", "messages/send"): {"id": "m1"}})
    make_service(session, None, ALT).send_to_self("Résumé", "a\n\tb café\n")
    [sent] = session.posted("messages/send")
    message = email.message_from_bytes(base64.urlsafe_b64decode(sent["raw"]), policy=policy.default)
    assert (message["Subject"], message.get_content()) == ("Résumé", "a\n\tb café\n")
