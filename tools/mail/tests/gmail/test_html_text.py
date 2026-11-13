"""Tests for html_to_text: drops scripts and styles, keeps readable structure."""

from mail_tool.gmail import html_to_text


def test_strips_script_style_and_title_but_keeps_text_and_structure() -> None:
    html = (
        "<html><head><title>Receipt</title><style>p {color: red}</style></head><body>"
        "<script>steal()</script><p>Hello&nbsp;&amp; welcome,</p>"
        "<div>Line   two<br>Line three</div><ul><li>one</li><li>two</li></ul></body></html>"
    )

    assert html_to_text(html) == "Hello & welcome,\n\nLine two\nLine three\n\n- one\n\n- two"
