"""Tests for audiohub.tts.blocks: joining markdown lines into spoken sentences."""

from audiohub.tts.blocks import join_blocks


def test_consecutive_prose_lines_form_one_sentence() -> None:
    assert join_blocks(["one long", "sentence here"]) == "one long sentence here."


def test_blank_line_separates_paragraphs() -> None:
    assert join_blocks(["First", "", "Second"]) == "First. Second."


def test_heading_stands_alone_even_without_a_blank_line() -> None:
    assert join_blocks(["# Title", "Body text"]) == "Title. Body text."


def test_list_item_continuation_joins_the_item() -> None:
    lines = ["- a long item", "  that wraps", "- next"]
    assert join_blocks(lines) == "a long item that wraps. next."


def test_existing_punctuation_is_not_doubled() -> None:
    assert join_blocks(
        ["Done!", "", "Ready?", "", "Note:", "", "Fine;", "", 'He said "stop."']
    ) == ('Done! Ready? Note: Fine; He said "stop."')


def test_full_stop_goes_after_closing_brackets_and_quotes() -> None:
    assert join_blocks(["(see above)", "", 'He said "hi"']) == '(see above). He said "hi".'


def test_no_lines_give_empty_text() -> None:
    assert join_blocks([]) == ""
    assert join_blocks(["", "   ", "---"]) == ""
