"""Paste keys, which press_key refuses because they type the owner's clipboard."""

import pytest

from browser_tool.gates import is_paste_key


@pytest.mark.parametrize(
    ("key", "pastes"),
    [
        ("Control+V", True),
        ("Meta+V", True),
        ("ControlOrMeta+V", True),
        ("Control+Shift+V", True),
        ("Shift+Insert", True),
        ("Control+C", False),
        ("Control+Insert", False),
        ("v", False),
        ("Shift+V", False),
    ],
)
def test_is_paste_key(key, pastes):
    assert is_paste_key(key) is pastes
