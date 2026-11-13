"""Tests for the server-side SVG sanitizer: the security boundary for `svg` items."""

import pytest

from whiteboard.display.scene import SceneError, sanitize_svg

SVG_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">'


def _clean(body: str) -> str:
    return sanitize_svg(f"{SVG_OPEN}{body}</svg>")


def test_keeps_ordinary_drawing() -> None:
    cleaned = _clean(
        '<g id="g1"><rect x="1" y="2" width="3" height="4" fill="url(#grad)"/>'
        '<use href="#g1"/><text>hello</text></g>'
    )
    for kept in ("<rect", 'fill="url(#grad)"', 'href="#g1"', "hello"):
        assert kept in cleaned


@pytest.mark.parametrize(
    ("body", "banned"),
    [
        ("<script>alert(1)</script>", "alert"),
        ("<SCRIPT>alert(1)</SCRIPT>", "alert"),
        ('<rect onload="alert(1)" ONCLICK="x()"/>', "alert"),
        ("<foreignObject><div>hi</div></foreignObject>", "div"),
        ('<image href="https://evil.example/x.png"/>', "evil"),
        ('<a xlink:href="javascript:alert(1)"><text>x</text></a>', "javascript"),
        ('<rect style="fill: url(https://evil.example/t)"/>', "evil"),
        ("<style>@import url(https://evil.example/s.css);</style>", "evil"),
        # Regression: a stylesheet restyled the whole page and lit up its hidden layers.
        ("<style>#night{opacity:1!important;background:#fff}</style>", "#night"),
        ('<a><set attributeName="xlink:href" to="javascript:alert(1)"/></a>', "javascript"),
        ('<x:script xmlns:x="http://www.w3.org/1999/xhtml">alert(1)</x:script>', "alert"),
    ],
)
def test_strips_dangerous_parts(body: str, banned: str) -> None:
    assert banned not in _clean(body)


@pytest.mark.parametrize("markup", ["<svg", "<html><body/></html>", "plain text"])
def test_rejects_non_svg(markup: str) -> None:
    with pytest.raises(SceneError):
        sanitize_svg(markup)
