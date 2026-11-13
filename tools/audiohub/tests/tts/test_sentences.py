"""Tests for audiohub.tts.sentences: sentence chunking for streaming synthesis."""

import pytest

from audiohub.tts import split_sentences

# Each of these is one sentence: an abbreviation or a dot inside a number or
# name must not end it.
ONE_SENTENCE = [
    "Mr. Smith arrived.",
    "Dr. Patel and Prof. Wu agreed.",
    "Use a tool, e.g. ruff, for linting.",
    "The U.S. team won.",
    "We meet at 5 p.m. on Friday.",
    "Smith et al. found it.",
    "Ask (dr. Who) now.",
    "Version 3.5 is out.",
    "It costs $3.50 today.",
    "Ping 192.168.0.1 first.",
    "Open config.toml please.",
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        (" \n\t ", []),
        ("just some words", ["just some words"]),
        (
            "Right then. I'm Claude! How can I help? Ask away.",
            ["Right then.", "I'm Claude!", "How can I help?", "Ask away."],
        ),
        ("Really?! Yes... Fine.", ["Really?!", "Yes...", "Fine."]),
        ("Neither did I. Then we left.", ["Neither did I.", "Then we left."]),
        ("Apples, pears, etc. Then we left.", ["Apples, pears, etc.", "Then we left."]),
        ("Pick option 3. Then save.", ["Pick option 3.", "Then save."]),
        (
            'He said "Stop." Then he left. (It was late.) Done.',
            ['He said "Stop."', "Then he left.", "(It was late.)", "Done."],
        ),
        ("One.\n\nTwo   words.\tThree.", ["One.", "Two words.", "Three."]),
        *[(sentence, [sentence]) for sentence in ONE_SENTENCE],
    ],
)
def test_split_sentences(text: str, expected: list[str]) -> None:
    assert split_sentences(text) == expected


def test_long_run_on_sentence_splits_at_clause_breaks() -> None:
    clause = "the kernel decides what to say next"
    text = ", ".join([clause] * 4) + "."
    chunks = split_sentences(text, max_chars=80)
    assert chunks == [f"{clause}, {clause},", f"{clause}, {clause}."]


def test_early_clause_break_loses_to_a_later_word_break() -> None:
    text = "Yes, " + "word " * 20
    chunks = split_sentences(text, max_chars=40)
    assert chunks[0] != "Yes,"
    assert all(len(chunk) <= 40 for chunk in chunks)


def test_unbreakable_token_is_hard_cut_at_the_limit() -> None:
    token = "x" * 95
    chunks = split_sentences(token, max_chars=40)
    assert chunks == ["x" * 40, "x" * 40, "x" * 15]


@pytest.mark.parametrize("max_chars", [20, 250])
def test_chunks_never_exceed_the_limit_and_lose_no_words(max_chars: int) -> None:
    text = (
        "Mr. Brown said, at 3.5 p.m. sharp, that the long-running build, "
        "which had failed twice already; was finally green — and nobody cared. "
        "Then a 60-character-identifier-with-no-spaces-at-all-anywhere-in-it showed up!"
    )
    chunks = split_sentences(text, max_chars=max_chars)
    assert all(0 < len(chunk) <= max_chars for chunk in chunks)
    assert "".join(chunks).replace(" ", "") == text.replace(" ", "")


def test_limit_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        split_sentences("Hello.", max_chars=0)
