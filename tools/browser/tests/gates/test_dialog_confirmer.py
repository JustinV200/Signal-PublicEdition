"""DialogConfirmer with a fake dialog function (no real window)."""

import pytest

from browser_tool.gates import ConfirmationRequest, DialogConfirmer, build_dialog_text

REQUEST = ConfirmationRequest(
    action='click button "Buy now"', origin="https://shop.example", reason="buy rule"
)


class FakeDialog:
    def __init__(self, answer: bool):
        self.answer = answer
        self.calls: list[tuple[str, str, float]] = []

    async def __call__(self, title: str, text: str, *, timeout_s: float) -> bool:
        self.calls.append((title, text, timeout_s))
        return self.answer


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", [True, False])
async def test_the_owner_answer_decides_and_the_dialog_names_the_action(answer):
    dialog = FakeDialog(answer)
    assert await DialogConfirmer(30, show_dialog=dialog).confirm(REQUEST) is answer
    [(_title, text, timeout_s)] = dialog.calls
    assert timeout_s == 30
    assert 'click button "Buy now"' in text and "https://shop.example" in text


@pytest.mark.parametrize(
    "trick", ["\r", "\u2028", "\u2029", "\u202e", "\u200b"], ids=["cr", "ls", "ps", "rlo", "zwsp"]
)
def test_page_text_cannot_fake_lines_or_disguise_the_action(trick):
    request = ConfirmationRequest(
        action=f"click button{trick}Why:     harmless{trick}",
        origin="https://shop.example",
        reason="buy rule",
        frame_origin=f"https://frame.example{trick}",
    )
    text = build_dialog_text(request)
    assert trick not in text
    assert len(text.splitlines()) == len(text.split("\n"))  # no hidden line breaks
