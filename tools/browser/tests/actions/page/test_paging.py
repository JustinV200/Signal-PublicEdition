"""Snapshot pages, ref subtrees and find over a canned redacted snapshot (pure)."""

import pytest

from browser_tool.actions.page.paging import find_matches, page_bounds, page_text, subtree

SNAPSHOT = "\n".join(
    [
        "- banner [ref=e1]:",
        '  - link "Home" [ref=e2]',
        "- main [ref=e3]:",
        '  - form "Compose" [ref=e4]:',
        '    - textbox "To" [ref=e5]: alice',
        '    - button "Send" [ref=e6]',
        "  - list:",
        '    - listitem: "Sent mail: weekly report"',
        '- contentinfo [ref=e7]: "send feedback"',
    ]
)


@pytest.mark.parametrize(
    ("max_chars", "page_count"),
    [
        (10_000, 1),  # fits: one page, as before paging
        (60, 6),  # cut after the last newline that fits, never mid-line
        (5, 51),  # lines longer than a page are cut mid-line, nothing is lost
    ],
)
def test_pages_cover_the_whole_snapshot_at_line_boundaries(max_chars, page_count):
    bounds = page_bounds(SNAPSHOT, max_chars)
    pages = [page_text(SNAPSHOT, bound) for bound in bounds]
    assert "".join(SNAPSHOT[start:end] for start, end in bounds) == SNAPSHOT
    assert len(pages) == page_count
    assert all(len(page) <= max_chars for page in pages)
    if max_chars == 60:
        assert pages[0] == '- banner [ref=e1]:\n  - link "Home" [ref=e2]'


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("e4", '  - form "Compose" [ref=e4]:\n    - textbox "To" [ref=e5]: alice\n'
               '    - button "Send" [ref=e6]'),
        ("e6", '    - button "Send" [ref=e6]'),
        ("e99", None),
    ],
)  # fmt: skip
def test_subtree_is_the_ref_line_and_everything_indented_under_it(ref, expected):
    assert subtree(SNAPSHOT, ref) == expected


def test_find_gives_line_page_ref_and_ancestors_case_insensitively():
    matches, total = find_matches(SNAPSHOT, "SEND", max_chars=120, max_results=1)
    assert total == 2  # the button and the footer; only the first is listed
    [button] = matches
    assert (button.line_no, button.page, button.ref) == (6, 2, "e6")
    assert button.path == ("main", 'form "Compose"')

    # A line with no ref of its own gets its nearest ancestor's.
    [item], _total = find_matches(SNAPSHOT, "weekly", max_chars=120, max_results=20)
    assert (item.line_no, item.ref, item.path) == (8, "e3", ("main", "list"))
