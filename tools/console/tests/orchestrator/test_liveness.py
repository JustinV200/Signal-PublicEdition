"""A claim is alive only while its inbox pipe is listed; no claim, or no listing, is not."""

import pytest
from signal_orchestrator.testing import fake_inbox, unused_pipe_address

from signal_console.orchestrator import Claim, is_claim_alive, liveness


def _refuse_listing(path: str) -> list[str]:
    raise FileNotFoundError(path)


@pytest.mark.parametrize("case", ["present", "absent", "no claim", "listing fails"])
async def test_a_claim_is_alive_only_while_its_pipe_is_listed(monkeypatch, case):
    # A real pipe served by a fake inbox, so the listing's own name format is what's matched.
    async with fake_inbox() as inbox:
        socket = unused_pipe_address() if case == "absent" else inbox.address
        claim = None if case == "no claim" else Claim(socket, "tok", None, "")
        if case == "listing fails":
            monkeypatch.setattr(liveness, "listdir", _refuse_listing)

        assert is_claim_alive(claim) is (case == "present")
