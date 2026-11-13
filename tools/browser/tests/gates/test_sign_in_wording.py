"""The wording a sign-in form's submit needs to skip the send rule (config)."""

import pytest

from browser_tool.config import SIGN_IN_WORDING_RE


@pytest.mark.parametrize(
    ("label", "is_sign_in"),
    [
        ("Sign in", True),
        ("LOGIN", True),
        ("Next →", True),
        ("Continue >", True),
        ("Log in Log in", True),  # aria-label and text both read
        ("Save changes", False),
        ("Post", False),
        ("Update", False),
        ("Go", False),
        ("Submit", False),  # the send word rule catches it anyway
        ("Sign in and pay", False),
        ("", False),
    ],
)
def test_sign_in_wording_is_the_whole_label(label, is_sign_in):
    assert bool(SIGN_IN_WORDING_RE.fullmatch(label)) is is_sign_in
