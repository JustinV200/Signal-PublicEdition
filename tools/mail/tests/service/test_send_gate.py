"""Send-dialog regressions: no recipient can be hidden, and odd recipient lists are refused."""

import pytest
from support.fakes import FakeOwner, FakeSession, make_service, text_part

from mail_tool.errors import SendRefused
from mail_tool.service.send_gate import MAX_DIALOG_CHARS

LONG_NAME = "Quarterly Planning Committee Distribution List For The Whole Department " * 2
ATTACKER = "attacker@evil.example"


def _draft_routes(headers: list[tuple[str, str]]) -> dict:
    message = {
        "id": "m5",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [{"name": name, "value": value} for name, value in headers],
            "parts": [text_part("text/plain", "line\n" * 50)],
        },
    }
    return {
        ("GET", "drafts/r-1"): {"id": "r-1", "message": message},
        ("POST", "drafts/send"): {"id": "m5", "threadId": "t1"},
    }


def test_an_attacker_hidden_among_long_named_recipients_is_shown_in_full() -> None:
    friends = [f'"{LONG_NAME}" <friend{n}@example.com>' for n in range(14)]
    to_header = ", ".join(friends[:7] + [f'"{LONG_NAME}" <{ATTACKER}>'] + friends[7:])
    headers = [
        ("To", to_header),
        ("Subject", "Minutes"),
        # A second To header, and a display name that looks like a different address.
        ("To", '"boss@example.com" <second-attacker@evil.example>'),
    ]
    session = FakeSession(_draft_routes(headers))
    owner = FakeOwner(answer=False)

    with pytest.raises(SendRefused):
        make_service(session, owner).send_draft("personal", "r-1")

    [(_title, text)] = owner.asked
    lines = text.split("\n")
    assert f"To: {ATTACKER}" in lines
    assert "To: second-attacker@evil.example" in lines
    assert all(f"To: friend{n}@example.com" in lines for n in range(14))
    assert "Recipients (16), each address in full:" in lines
    assert len(text) <= MAX_DIALOG_CHARS  # the dialog never has to elide the middle
    assert session.posted("drafts/send") == []


@pytest.mark.parametrize(
    ("to_header", "reason"),
    [
        (", ".join(f"p{n}@example.com" for n in range(21)), "at most 20"),
        ("good@example.com <evil@example.net>", "can't be read safely"),
    ],
)
def test_too_many_or_unreadable_recipients_are_refused_without_a_dialog(to_header, reason) -> None:
    session = FakeSession(_draft_routes([("To", to_header)]))
    owner = FakeOwner(answer=True)

    with pytest.raises(SendRefused, match=reason):
        make_service(session, owner).send_draft("personal", "r-1")

    assert owner.asked == []
    assert session.posted("drafts/send") == []
