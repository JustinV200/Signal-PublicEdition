"""Tests for the near-duplicate and code-heavy text heuristics."""

import pytest

from audiohub.kernel.dispatch.text_checks import is_code_heavy, is_near_duplicate

PADDING = "Status from the nightly pipeline for signal-web on the main branch, run 4182. " * 3


@pytest.mark.parametrize(
    ("delivered", "dropped", "is_repeat"),
    [
        ("Tests passed: 214 of 214.", "Tests passed: 214 of 214", True),
        ("Tests passed: 214 of 214.", "Tests  passed:\n214 of 214. ", True),
        # Contradicting or merely similar pairs: every one must be delivered.
        ("Deploy to production succeeded.", "Deploy to production failed.", False),
        ("Tests passed: 214 of 214.", "Tests failed: 12 of 214.", False),
        ("meeting at 3 pm", "meeting at 5 pm", False),
        (PADDING + "The build is green.", PADDING + "The build is red.", False),
        ("Not all tests passed.", "All tests passed.", False),
        ("Budget is $1,000,000.", "Budget is $1,000.", False),
        ("Temperature 5", "Temperature −5", False),
        ("x = y", "x != y", False),
        ("Build ❌", "Build ✅", False),
        ("Error rate 5%", "Error rate .5%", False),
        ("Scale 10⁶", "Scale 106", False),
        ("Balance (500)", "Balance 500", False),
        ("Output 5 mW", "Output 5 MW", False),
        ("Tests passed: 214 of 214.", "tests passed, 214 of 214", False),
    ],
)
def test_only_exact_repeats_count_as_duplicates(delivered, dropped, is_repeat) -> None:
    assert is_near_duplicate(dropped, delivered) is is_repeat


@pytest.mark.parametrize(
    "text",
    [
        "Here:\n```python\nprint('hi')\n```",
        "KeyError {'user_id'} in src/app/main.py; see /var/log/app.log",
        "Changed files:\n- src/a.py\n- src/b.py\n- tests/test_a.py",
        "Steps:\n1. build\n2. test\n3. deploy",
    ],
    ids=["fence", "symbols", "bullet-list", "numbered-list"],
)
def test_code_and_lists_are_code_heavy(text) -> None:
    assert is_code_heavy(text)


@pytest.mark.parametrize(
    "text",
    [
        "Your next meeting is at 3 pm with Sam, about the Signal launch plan.",
        "I'd like to run git push origin main. Should I go ahead?",
        "Tests passed.\nDeploy is next.\nNothing else to report.",
    ],
)
def test_plain_speech_is_not_code_heavy(text) -> None:
    assert not is_code_heavy(text)
