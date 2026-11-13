"""Sending to the orchestrator's inbox, against a fake Claude Code named-pipe server."""

import pytest

from signal_orchestrator import Claim, InboxError, send_to_inbox
from signal_orchestrator.testing import fake_inbox, unused_pipe_address

TEXT = 'the owner: put "lecture" up\nthen stop'


async def test_send_writes_the_auth_line_then_the_message():
    async with fake_inbox() as inbox:
        await send_to_inbox(Claim(inbox.address, "tok123", None, ""), TEXT)

    assert inbox.frames() == [
        {"type": "auth", "token": "tok123"},
        {"type": "user", "message": {"role": "user", "content": TEXT}},
    ]


@pytest.mark.parametrize("inbox", ["refuses", "absent"])
async def test_send_reports_an_inbox_that_refuses_or_isnt_there(inbox):
    async with fake_inbox(is_refusing=True) as refusing:
        address = refusing.address if inbox == "refuses" else unused_pipe_address()
        with pytest.raises(InboxError):
            await send_to_inbox(Claim(address, "tok123", None, ""), TEXT)
