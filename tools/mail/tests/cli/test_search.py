"""Regression: `mail search` prints a bare JSON list by default, even when Gmail pages.

tools/mail-digest parses this output and raises if it isn't a list.
"""

import json

import pytest
from support.fakes import PERSONAL, SAMPLE_HEADERS, FakeSession, FakeStore, gmail_message

from mail_tool.cli import main
from mail_tool.service import factory


def test_search_default_output_is_a_list_even_with_a_next_page_token(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    session = FakeSession(
        {
            ("GET", "messages"): {"messages": [{"id": "m1"}], "nextPageToken": "tok2"},
            ("GET", "messages/m1"): gmail_message("m1", SAMPLE_HEADERS),
        }
    )
    monkeypatch.setattr(factory, "TokenStore", lambda _folder: FakeStore(PERSONAL))
    monkeypatch.setattr(factory, "GoogleSessions", lambda _path: lambda _record: session)

    main(["search", "personal", ""])
    assert isinstance(json.loads(capsys.readouterr().out), list)
    main(["search", "personal", "", "--paged"])
    assert json.loads(capsys.readouterr().out)["next_page_token"] == "tok2"
