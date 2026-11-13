"""Security table for assignment_check.findings: what the reader says is believed only if the
page's own text backs it up."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mail_digest.assignment_check.check_config import load_check_config
from mail_digest.assignment_check.courses import CLASSROOM, MOODLE, site_pages
from mail_digest.assignment_check.findings import Item, SiteReading, check_findings
from mail_digest.assignment_check.findings.flags import flagged
from mail_digest.assignment_check.reader import ReaderItem, ReaderOutput
from mail_digest.assignment_check.visit import SiteVisit, VisitedPage

CONFIG = load_check_config(Path(__file__).with_name("check_config.toml"))
CLASSROOM_ACCOUNT = CONFIG.classroom_account
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone(timedelta(hours=-4)))
MOODLE_PAGE = "hist-205-assign"
MOODLE_TEXT = """- table:
  - row "Practice Quiz Thursday, 15 October 2026, 5:00 PM No submission":
    - link "Practice Quiz":
      - /url: https://lms.example.edu/mod/assign/view.php?id=4101
  - row "Project Demo Monday, 26 October 2026, 8:30 AM Submitted for grading":
    - link "Project Demo":
      - /url: /mod/assign/view.php?id=4102
  - row "Visit www.evil.example now":
    - link "Visit www.evil.example now":
      - /url: /mod/assign/view.php?id=4103
  - row "Homework 3 Friday, 16 October 2026 Submitted for grading":
    - link "Homework 3":
      - /url: /mod/assign/view.php?id=4105
  - row "Homework Friday, 23 October 2026 No submission":
    - link "Homework":
      - /url: /mod/assign/view.php?id=4106
  - row "Code 123456 here":
    - link "Code 123456 here":
      - /url: /mod/assign/view.php?id=4104
- paragraph: Submitted for grading
"""
CLASS_NAME = CONFIG.courses[-1].class_name
CLASS_ID = CONFIG.courses[-1].site_id
CLASSROOM_TEXT = f"""- banner: {CLASSROOM_ACCOUNT}
- listitem "A18 Sorting {CLASS_NAME}":
  - link "A18 Sorting":
    - /url: /u/1/c/{CLASS_ID}/a/ODk1MTIz/details
- listitem "A19 Other class":
  - link "A19 Other class":
    - /url: /u/1/c/T3RoZXJjbGFzcw/a/ODk1MTI0/details
"""


def _item(name, ref, page=MOODLE_PAGE, status_text="", class_name="", due="2026-10-26 08:30"):
    return ReaderItem(page, name, class_name, "assignment", due, status_text, ref)


def _site(site, texts, items, suspicious=()):
    """Every page of site ok and readable, with texts[key] as its text (default: the account)."""
    pages = site_pages(site, CONFIG)
    default = CLASSROOM_ACCOUNT if site == CLASSROOM else ""
    visit = SiteVisit(
        "ok", tuple(VisitedPage(p.key, "ok", texts.get(p.key, default)) for p in pages)
    )
    reading = ReaderOutput(
        readable=frozenset(p.key for p in pages),
        accounts={},
        items=tuple(items),
        suspicious=frozenset(suspicious),
    )
    return SiteReading(pages, visit, reading)


def _moodle(items, suspicious=()):
    return _site(MOODLE, {MOODLE_PAGE: MOODLE_TEXT}, items, suspicious)


@pytest.mark.parametrize(
    ("items", "suspicious", "expected"),
    [
        # Status comes from the phrase on the item's own row, the link from the page's.
        (
            [_item("Project Demo", "4102", status_text="Submitted for grading")],
            (),
            [("Project Demo", "done", "https://lms.example.edu/mod/assign/view.php?id=4102")],
        ),
        # An invented name, or a ref that isn't in the page's links.
        ([_item("Bonus Project", "4102")], (), []),
        ([_item("Project Demo", "9999")], (), []),
        # A status phrase that's on the page but not on the item's row changes nothing.
        (
            [_item("Practice Quiz", "4101", status_text="Submitted for grading")],
            (),
            [
                (
                    "Practice Quiz",
                    "unknown",
                    "https://lms.example.edu/mod/assign/view.php?id=4101",
                )
            ],
        ),
        # "Homework" can't take "Homework 3"'s row, or pass as its name.
        (
            [_item("Homework", "4106", status_text="Submitted for grading")],
            (),
            [("Homework", "unknown", "https://lms.example.edu/mod/assign/view.php?id=4106")],
        ),
        ([_item("Homework", "4105", status_text="Submitted for grading")], (), []),
        # Names on the page that hold a www. link or a 6+ digit number.
        ([_item("Visit www.evil.example now", "4103")], (), []),
        ([_item("Code 123456 here", "4104")], (), []),
        # A suspicious page loses its items (and its course).
        ([_item("Project Demo", "4102")], (MOODLE_PAGE,), []),
    ],
    ids=[
        "valid",
        "invented-name",
        "ref-not-on-page",
        "status-off-line",
        "other-row-status",
        "other-row-ref",
        "www",
        "long-number",
        "suspicious",
    ],
)
def test_moodle_items_are_checked_against_the_page(items, suspicious, expected):
    findings = check_findings([_moodle(items, suspicious)], NOW)
    assert [(i.name, i.status, i.link) for i in findings.items] == expected


@pytest.mark.parametrize(
    ("text", "item", "expected"),
    [
        (
            CLASSROOM_TEXT,
            _item("A18 Sorting", "ODk1MTIz", class_name=CLASS_NAME),
            ["A18 Sorting"],
        ),
        # The page doesn't show the school account.
        (
            CLASSROOM_TEXT.replace(CLASSROOM_ACCOUNT, "someone@gmail.com"),
            _item("A18 Sorting", "ODk1MTIz", class_name=CLASS_NAME),
            [],
        ),
        # Another class's item, by its link or by the class the reader names.
        (CLASSROOM_TEXT, _item("A19 Other class", "ODk1MTI0", class_name=CLASS_NAME), []),
        (CLASSROOM_TEXT, _item("A18 Sorting", "ODk1MTIz", class_name="Other class"), []),
    ],
    ids=["valid", "wrong-account", "other-class-link", "other-class-name"],
)
def test_classroom_items_need_the_account_and_the_course_class(text, item, expected):
    page = "chem-120-turned-in"
    findings = check_findings([_site(CLASSROOM, {page: text}, [replace(item, page=page)])], NOW)
    assert [i.name for i in findings.items] == expected
    # Status comes from the list the page is, never the model.
    assert all(i.status == "done" for i in findings.items)


# A link with no /url line of its own, straight before another item's link.
NO_URL_TEXT = """- table:
  - row "Homework Friday, 23 October 2026 No submission":
    - link "Homework":
    - link "Homework 3":
      - /url: /mod/assign/view.php?id=4105
"""
# A table, then a sidebar block that links to "Homework" again after the last row.
SIDEBAR_TEXT = """- table:
  - row "Homework Friday, 23 October 2026 No submission":
    - link "Homework":
      - /url: /mod/assign/view.php?id=4106
  - row "Homework 3 Friday, 16 October 2026 Submitted for grading":
    - link "Homework 3":
      - /url: /mod/assign/view.php?id=4105
- complementary:
  - link "Homework":
    - /url: /mod/assign/view.php?id=4106
"""


# Two items with the same name: id=1 was submitted, id=2 wasn't.
DUPLICATE_TEXT = """- table:
  - row "Homework Thursday, 1 October 2026 Submitted for grading":
    - link "Homework":
      - /url: /mod/assign/view.php?id=1
  - row "Homework Thursday, 8 October 2026 No submission":
    - link "Homework":
      - /url: /mod/assign/view.php?id=2
"""
# An item named like a status phrase, in a row that says something else.
PHRASE_NAME_TEXT = """- table:
  - row "Submitted for grading Thursday, 8 October 2026 No submission":
    - link "Submitted for grading":
      - /url: /mod/assign/view.php?id=3
"""
# The only "Homework" link sits in Homework 2's row, next to Homework 2's own link.
SHARED_ROW_TEXT = """- table:
  - row "Homework 2 Thursday, 8 October 2026 Submitted for grading":
    - link "Homework 2":
      - /url: /mod/assign/view.php?id=2
    - link "Homework":
      - /url: /mod/assign/view.php?id=1
"""
# The same name and ref twice, in rows that disagree.
SAME_REF_TEXT = """- table:
  - row "Homework Submitted for grading":
    - link "Homework":
      - /url: /mod/assign/view.php?id=1
  - row "Homework No submission":
    - link "Homework":
      - /url: /mod/assign/view.php?id=1
"""
# Taking the name out must not glue its two sides into a phrase.
GLUED_TEXT = """- table:
  - row "Lab Submitted forLabgrading":
    - link "Lab":
      - /url: /mod/assign/view.php?id=1
"""
# Playwright single-quotes a whole key holding ": ", " #", "{", "}" or a backtick.
QUOTED_LINK_TEXT = """- table [ref=e1]:
  - 'row "Lab 3: Arrays Friday, 23 October 2026 Submitted for grading" [ref=e2]':
    - 'link "Lab 3: Arrays" [ref=e4] [cursor=pointer]':
      - /url: /mod/assign/view.php?id=1
"""
QUOTED_ROW_TEXT = """- table:
  - 'row "Homework Due: Friday Submitted for grading"':
    - link "Homework":
      - /url: /mod/assign/view.php?id=1
"""
QUOTED_EXTRA_LINK_TEXT = """- table:
  - row "Homework Submitted for grading":
    - link "Homework":
      - /url: /mod/assign/view.php?id=1

    - 'link "Rubric: v2"':
      - /url: /mod/assign/view.php?id=7
"""


@pytest.mark.parametrize(
    ("text", "name", "ref", "expected"),
    [
        (QUOTED_LINK_TEXT, "Lab 3: Arrays", "1", [("Lab 3: Arrays", "done")]),
        (QUOTED_ROW_TEXT, "Homework", "1", [("Homework", "done")]),
        # Also after a blank line, an extra link is still in the row.
        (QUOTED_EXTRA_LINK_TEXT, "Homework", "1", [("Homework", "unknown")]),
        (NO_URL_TEXT, "Homework", "4105", []),
        (SIDEBAR_TEXT, "Homework", "4106", [("Homework", "unknown")]),
        (DUPLICATE_TEXT, "Homework", "2", [("Homework", "unknown")]),
        (DUPLICATE_TEXT, "Homework", "1", [("Homework", "done")]),
        (PHRASE_NAME_TEXT, "Submitted for grading", "3", [("Submitted for grading", "unknown")]),
        (SHARED_ROW_TEXT, "Homework", "1", [("Homework", "unknown")]),
        (SAME_REF_TEXT, "Homework", "1", [("Homework", "unknown")]),
        (GLUED_TEXT, "Lab", "1", [("Lab", "unknown")]),
    ],
    ids=[
        "quoted-link",
        "quoted-row",
        "quoted-extra-link-after-blank",
        "link-without-url-borrows-none",
        "sidebar-link-borrows-no-row",
        "same-name-other-row",
        "same-name-own-row",
        "phrase-in-name",
        "row-with-two-links",
        "same-ref-twice",
        "name-removal-glues-no-phrase",
    ],
)
def test_odd_layouts_fail_closed(text, name, ref, expected):
    item = _item(name, ref, status_text="Submitted for grading")
    findings = check_findings([_site(MOODLE, {MOODLE_PAGE: text}, [item])], NOW)
    assert [(i.name, i.status) for i in findings.items] == expected


def test_items_with_the_same_name_stay_apart():
    items = [
        _item("Homework", "1", status_text="Submitted for grading"),
        _item("Homework", "2", status_text="No submission"),
    ]
    findings = check_findings([_site(MOODLE, {MOODLE_PAGE: DUPLICATE_TEXT}, items)], NOW)
    assert [(i.link[-4:], i.status) for i in findings.items] == [("id=1", "done"), ("id=2", "open")]


@pytest.mark.parametrize(
    ("site", "statuses", "expected"),
    [
        (MOODLE, ("unknown", "done"), "done"),
        # Two trusted statuses that disagree: unknown, never first-wins.
        (MOODLE, ("done", "open"), "unknown"),
        # Classroom: one item on two lists, the worse list wins; done never beats it.
        (CLASSROOM, ("done", "missing"), "missing"),
        (CLASSROOM, ("open", "done"), "open"),
    ],
    ids=["trusted-beats-unknown", "disagree", "classroom-missing", "classroom-open"],
)
def test_one_item_seen_twice(site, statuses, expected):
    seen = [Item("chem-120", site, "A18", "assignment", "", s, "https://x/1") for s in statuses]
    [item] = flagged(seen, NOW)
    assert item.status == expected


def test_merge_keeps_a_due_date_from_the_unknown_copy():
    trusted = Item("chem-120", MOODLE, "A18", "assignment", "", "open", "https://x/1")
    unknown = replace(trusted, status="unknown", due="2026-10-26 08:30")
    for seen in ([trusted, unknown], [unknown, trusted]):
        [item] = flagged(seen, NOW)
        assert (item.status, item.due) == ("open", "2026-10-26 08:30")


def test_items_are_capped_per_page():
    rows = "".join(
        f'- row "Task {n}":\n  - link "Task {n}":\n    - /url: /mod/assign/view.php?id={n}\n'
        for n in range(1, 63)
    )
    items = [_item(f"Task {n}", str(n)) for n in range(1, 63)]
    findings = check_findings([_site(MOODLE, {MOODLE_PAGE: rows}, items)], NOW)
    assert len(findings.items) == 60


def test_a_problem_page_leaves_its_whole_course_out_and_flags_are_the_runners():
    site = _moodle([_item("Practice Quiz", "4101", due="2026-10-15 17:00")])
    # Another hist-205 page needed a login, so the course isn't touched this check.
    pages = tuple(
        VisitedPage(p.key, "login_needed") if p.key == "hist-205-quiz" else p
        for p in site.visit.pages
    )
    blocked = SiteReading(site.pages, SiteVisit("ok", pages), site.reading)
    assert check_findings([blocked], NOW).items == ()
    assert {(p.course, p.reason) for p in check_findings([blocked], NOW).problems} == {
        ("hist-205", "login_needed")
    }
    # Past due, but with no status the runner trusts: it may be handed in, so not overdue.
    [item] = check_findings([site], NOW).items
    assert item.status == "unknown" and not item.overdue and not item.due_soon
