"""Security boundary for `mail send-self`: it only ever mails SELF_ADDRESS, from its own account.

Runs the real CLI and build_service, faking only the saved accounts, the mail.toml
file and Gmail. No argument, env var or config key may change the recipient.
"""

import base64
import contextlib
import email
from email import policy
from pathlib import Path

import pytest
from support.fakes import ALT, PERSONAL, FakeSession, FakeStore

from mail_tool.cli import main
from mail_tool.config import load_settings
from mail_tool.service import SELF_ADDRESS, factory

EVIL = "evil@example.com"
SEND_PATH = "messages/send"


class Attempt:
    """One try at redirecting the send: extra CLI args, env vars, a mail.toml, the text."""

    def __init__(self, args=(), env=None, config="", subject="Signal digest", body="hi\n"):
        self.args, self.env, self.config = list(args), env or {}, config
        self.subject, self.body = subject, body


ATTEMPTS = {
    "plain send": (Attempt(), True),
    "--to flag": (Attempt(args=["--to", EVIL]), False),
    "--bcc flag": (Attempt(args=["--bcc", EVIL]), False),
    "positional address": (Attempt(args=[EVIL]), False),
    "header in the subject": (Attempt(subject=f"Hi\r\nBcc: {EVIL}"), False),
    "headers in the body": (Attempt(body=f"To: {EVIL}\nBcc: {EVIL}\n\nhi\n"), True),
    "env vars": (Attempt(env={"MAIL_TO": EVIL, "MAIL_SELF_ADDRESS": EVIL, "TO": EVIL}), True),
    "config key": (Attempt(config=f'[send]\nself_address = "{EVIL}"\n'), False),
    "config section": (Attempt(config=f'[self]\nto = "{EVIL}"\n'), False),
}


@pytest.mark.parametrize(("attempt", "is_sent"), ATTEMPTS.values(), ids=ATTEMPTS.keys())
def test_send_self_only_ever_mails_self_address(
    attempt: Attempt, is_sent: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = FakeSession({("POST", SEND_PATH): {"id": "m1"}})
    opened = []
    config_path = tmp_path / "mail.toml"
    if attempt.config:
        config_path.write_text(attempt.config, encoding="utf-8")

    def open_session(record):
        opened.append(record)
        return session

    monkeypatch.setattr(factory, "TokenStore", lambda _folder: FakeStore(PERSONAL, ALT))
    monkeypatch.setattr(factory, "GoogleSessions", lambda _path: open_session)
    monkeypatch.setattr(factory, "load_settings", lambda: load_settings(config_path))
    for name, value in attempt.env.items():
        monkeypatch.setenv(name, value)
    body_file = tmp_path / "body.txt"
    body_file.write_text(attempt.body, encoding="utf-8")
    argv = ["send-self", "--subject", attempt.subject, "--body-file", str(body_file)]

    # SystemExit: argparse refusing an unknown option or argument.
    with contextlib.suppress(SystemExit):
        main([*argv, *attempt.args])

    sends = [_parse(sent["raw"]) for sent in session.posted(SEND_PATH)]
    assert len(sends) == (1 if is_sent else 0)
    assert all(record.email == SELF_ADDRESS for record in opened)
    for message in sends:
        assert message.get_all("To") == [SELF_ADDRESS]
        assert not any(message.get_all(name) for name in ("Cc", "Bcc", "Resent-To"))
        assert message.get_content_type() == "text/plain"  # one plain part, no attachments


def _parse(raw: str) -> email.message.EmailMessage:
    """A sent `raw` message, parsed."""
    return email.message_from_bytes(base64.urlsafe_b64decode(raw), policy=policy.default)
