"""Per-fill confirmation: names the credential and live origin and strips control characters."""

import pytest

from vault.confirm import ConfirmRequest, DialogConfirmer

REQUEST = ConfirmRequest(
    credential_id="github",
    credential_name="GitHub\n\u2028Origin:\u2029   https://github.com\u202e",
    top_origin="https://evil.test",
    frame_origin="https://evil.test",
)


@pytest.mark.asyncio
async def test_dialog_shows_the_live_origin_and_strips_control_characters():
    shown = []

    async def fake_ask(title: str, text: str, *, timeout_s: float) -> bool:
        shown.append(text)
        return False

    assert await DialogConfirmer(ask=fake_ask).confirm(REQUEST) is False
    text = shown[0]
    assert "Site origin: https://evil.test" in text
    # The (unverified) name can't start a fake "Origin:" line or reorder the text.
    assert not any(line.startswith("Origin:") for line in text.splitlines())
    assert "\u202e" not in text
    assert "Credential: GitHub Origin: https://github.com (github)" in text
    assert "Login frame origin" not in text
