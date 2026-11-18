"""The deterministic edits: the address constants and the samples' sent-mail cleanup."""

from collections.abc import Callable
from pathlib import Path

import pytest

from signal_setup.samples.sent_mail import own_text
from signal_setup.wiring import set_constant

RepoFile = Callable[[str], Path]  # the conftest `repo_file` fixture


def test_set_constant_rewrites_one_line_and_keeps_crlf(tmp_path: Path) -> None:
    source = tmp_path / "self_send.py"
    source.write_bytes(b'"""Doc."""\r\nSELF_ADDRESS = "owner@example.com"\r\nOTHER = 1\r\n')
    set_constant(source, "SELF_ADDRESS", "me@mail.example")
    assert source.read_bytes() == b'"""Doc."""\r\nSELF_ADDRESS = "me@mail.example"\r\nOTHER = 1\r\n'
    for bad in ('x" + evil + "', "no-at-sign", "a b@c.d"):
        with pytest.raises(ValueError):
            set_constant(source, "SELF_ADDRESS", bad)


def test_own_text_drops_quotes_and_wrapper() -> None:
    body = (
        "<untrusted_email_content>Sounds good, see you then.\n> earlier line\n\n"
        "On Mon, Jan 1, 2026 at 9:00 AM Someone <a@b.c> wrote:\n"
        "> quoted</untrusted_email_content>"
    )
    assert own_text(body) == "Sounds good, see you then."


def test_readme_starts_with_the_intro(repo_file: RepoFile) -> None:
    from signal_setup.intro import intro_text

    assert intro_text() in repo_file("README.md").read_text("utf-8")
