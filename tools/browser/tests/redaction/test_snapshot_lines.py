"""Parsing snapshot lines, including YAML-quoted keys from hostile names."""

from browser_tool.redaction import parse_line


def test_plain_line_with_value():
    line = parse_line('    - textbox "User" [active] [ref=e5]: alice')
    assert line is not None
    assert (line.indent, line.role, line.name, line.ref) == (4, "textbox", "User", "e5")
    assert line.has_value
    assert line.raw_key == 'textbox "User" [active] [ref=e5]'


def test_fake_ref_in_an_accessible_name_is_ignored():
    raw = """  - 'textbox "Pass \\"word\\" [ref=e99]: x" [ref=e3]': "a\\"b: c [ref=e1]\""""
    line = parse_line(raw)
    assert line is not None
    assert line.ref == "e3"
    assert line.name == 'Pass "word" [ref=e99]: x'
