"""Tests for audiohub.tts.cleaning: markdown, code and URLs out, speakable prose in."""

import pytest

from audiohub.tts import clean_for_speech


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Right then, all done.", "Right then, all done."),
        ("", ""),
        ("  \n\t\n ", ""),
        ("The **build** passed.", "The build passed."),
        ("The __build__ passed.", "The build passed."),
        ("It is _really_ fine.", "It is really fine."),
        ("It is *really* fine.", "It is really fine."),
        ("The ~~old~~ new way.", "The old new way."),
        ("***Very*** important.", "Very important."),
        # Lookalike emphasis is left alone.
        ("Set my_var_name to one.", "Set my_var_name to one."),
        ("Compute 2*3*4 first.", "Compute 2*3*4 first."),
        ("Pass **kwargs through.", "Pass **kwargs through."),
        # Inline code keeps its text and protects what's inside.
        ("Edit `__init__.py` and `*args`.", "Edit __init__.py and *args."),
        ("Call **`load_config`** first.", "Call load_config first."),
        ("Odd 0 text `x`.", "Odd 0 text x."),
    ],
)
def test_inline_markup(text: str, expected: str) -> None:
    assert clean_for_speech(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("See https://example.com/docs for more.", "See a link for more."),
        ("Read http://x.io/a?b=1&c=2 today.", "Read a link today."),
        ("Try www.example.com instead.", "Try a link instead."),
        ("Links: https://a.io, https://b.io.", "Links: a link, a link."),
        ("(see https://example.com/x)", "(see a link)."),
        ("Open <https://example.com/x> now.", "Open a link now."),
        ("(see https://en.wikipedia.org/wiki/Foo_(bar))", "(see a link)."),
        ("Visit **https://x.io** now.", "Visit a link now."),
        ("Read [the guide](https://x.io/guide).", "Read the guide."),
        (
            "Fixed in [`load_config`](src/config.py#L10) and [main.py](src/main.py).",
            "Fixed in load_config and main.py.",
        ),
        ("Run `curl https://x.io/api` now.", "Run curl a link now."),
        ("Read [Foo](https://en.wikipedia.org/wiki/Foo_(bar)) today.", "Read Foo today."),
        ("![A cat](https://x.io/cat.png)", "A cat."),
    ],
)
def test_links_and_urls(text: str, expected: str) -> None:
    assert clean_for_speech(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# Summary\nThe tests pass.", "Summary. The tests pass."),
        ("###### Summary\nThe tests pass.", "Summary. The tests pass."),
        ("#hashtag time", "#hashtag time."),
        (
            "Two things:\n- first item\n* second item\n+ third item",
            "Two things: first item. second item. third item.",
        ),
        ("1. Install uv\n2) Run the tests", "Install uv. Run the tests."),
        ("3.5 is the version.", "3.5 is the version."),
        ("> Quoted words.\n>> Deeper.", "Quoted words. Deeper."),
        *[
            (f"Above.\n{rule}\nBelow.", "Above. Below.")
            for rule in ("---", "***", "_____", "- - -", "=====")
        ],
        (
            "This sentence was\nhard wrapped by an editor.",
            "This sentence was hard wrapped by an editor.",
        ),
        ("First idea\n\nSecond idea", "First idea. Second idea."),
        ("# Title\r\n\r\nSome\ttext  here.", "Title. Some text here."),
    ],
)
def test_block_structure(text: str, expected: str) -> None:
    assert clean_for_speech(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Here's the fix:\n```python\nprint('hi')\n```\nThat works.",
            "Here's the fix: code omitted. That works.",
        ),
        (
            "One:\n```\na\n```\nTwo:\n```\nb\n```\nDone.",
            "One: code omitted. Two: code omitted. Done.",
        ),
        ("Try:\n~~~\nls -la\n~~~", "Try: code omitted."),
        ("Code:\n```\na\n`````\nAfter.", "Code: code omitted. After."),
        ("```x``` is handy.\nMore text.", "x is handy. More text."),
        ("````\n```\nstill code\n~~~~\n````\nAfter.", "code omitted. After."),
        ("```\ncurl https://example.com\n```", "code omitted."),
    ],
    ids=[
        "block",
        "separate-blocks",
        "tilde",
        "longer-closer",
        "inline-triple-backticks",
        "inner-fence-is-code",
        "url-in-block",
    ],
)
def test_fenced_blocks(text: str, expected: str) -> None:
    assert clean_for_speech(text) == expected


def test_unclosed_fence_swallows_the_rest() -> None:
    text = "Partial reply:\n```bash\nrm -rf build\nmore code"
    assert clean_for_speech(text) == "Partial reply: code omitted."


def test_realistic_reply_reads_cleanly() -> None:
    reply = (
        "## Done\n\n"
        "I fixed the **bug** in `parse_config`. Changes:\n\n"
        "- Updated the [loader](https://github.com/x/y/blob/main/loader.py)\n"
        "- Added a test\n\n"
        "```python\ndef f():\n    return 1\n```\n\n"
        "Want me to run the suite?"
    )
    assert clean_for_speech(reply) == (
        "Done. I fixed the bug in parse_config. Changes: Updated the loader. "
        "Added a test. code omitted. Want me to run the suite?"
    )
