"""Sanitizing untrusted dialog text: no fake lines, no hidden or reordered text, both ends kept."""

from signal_confirm import sanitize_text
from signal_confirm.sanitize import ELISION, sanitize_message


def test_controls_formats_and_separators_become_single_spaces():
    text = "GitHub\n\u2028Origin:\u2029   https://github.com\u202e\t\x00end "
    assert sanitize_text(text, 200) == "GitHub Origin: https://github.com end"


def test_long_text_keeps_its_head_and_tail_at_exactly_the_cap():
    shown = sanitize_text("head" + "x" * 200 + "TAIL", 60)
    assert len(shown) == 60
    assert shown.startswith("head") and shown.endswith("TAIL") and ELISION in shown


def test_message_keeps_its_own_line_breaks_but_none_hidden_in_a_line():
    message = "Line one\u2028Origin: fake\r\n\n\n\nLine\u202e two"
    assert sanitize_message(message, 500) == "Line one Origin: fake\n\nLine two"
