"""Tests for mail_digest.kb.targets: finding this week's plan and the current term's courses."""

import _winapi
from datetime import date

import pytest

from mail_digest.kb import find_targets, snapshot, week_folder_name

MONDAY = date(2026, 10, 19)


@pytest.mark.parametrize(
    ("day", "folder"),
    [
        (date(2026, 10, 19), "2026-10-19-to-10-25"),  # Monday
        (date(2026, 10, 25), "2026-10-19-to-10-25"),  # Sunday, same week
        (date(2027, 1, 1), "2026-12-28-to-01-03"),  # across New Year: the Monday's year
    ],
)
def test_week_folder_name_is_the_monday_to_sunday_range(day, folder):
    assert week_folder_name(day) == folder


def _touch(root, relative):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_finds_this_weeks_plan_and_its_terms_courses(tmp_path):
    _touch(tmp_path, "inbox.md")
    _touch(tmp_path, "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md")
    _touch(tmp_path, "terms/2026-fall/courses/cs-102-os/README.md")
    _touch(tmp_path, "terms/2026-spring/weeks/2026-03-02-to-03-08/plan.md")
    _touch(tmp_path, "terms/2026-spring/courses/old-course/README.md")
    targets = find_targets(tmp_path, MONDAY)
    assert targets.week == "2026-10-19-to-10-25"
    assert targets.plan == "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md"
    # Term names don't sort by date (fall < spring), so the term comes from the weeks.
    assert targets.courses == ("terms/2026-fall/courses/cs-102-os/README.md",)
    assert targets.editable == (
        "inbox.md",
        "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md",
        "terms/2026-fall/courses/cs-102-os/README.md",
    )


def test_missing_plan_or_inbox_still_names_the_latest_terms_courses(tmp_path):
    _touch(tmp_path, "terms/2026-fall/weeks/2026-10-12-to-10-18/plan.md")
    _touch(tmp_path, "terms/2026-fall/courses/hist-205/README.md")
    targets = find_targets(tmp_path, MONDAY)
    assert targets.plan is None
    assert targets.courses == ("terms/2026-fall/courses/hist-205/README.md",)
    # No inbox.md file, so no Edit(/inbox.md) rule: it would let the job create inbox.md/x.
    assert targets.editable == ("terms/2026-fall/courses/hist-205/README.md",)


def test_a_course_name_that_cant_be_an_exact_edit_rule_is_skipped(tmp_path):
    _touch(tmp_path, "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md")
    _touch(tmp_path, "terms/2026-fall/courses/odd (copy)/README.md")
    _touch(tmp_path, "terms/2026-fall/courses/hist-205/README.md")
    targets = find_targets(tmp_path, MONDAY)
    assert targets.courses == ("terms/2026-fall/courses/hist-205/README.md",)


def test_a_junctioned_course_folder_is_skipped_by_targets_and_the_snapshot(tmp_path):
    # A junction needs no admin rights, and os.walk follows one like a plain folder.
    life, outside = tmp_path / "life", tmp_path / "outside"
    _touch(life, "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md")
    _touch(life, "terms/2026-fall/courses/hist-205/README.md")
    _touch(outside, "README.md")
    _winapi.CreateJunction(str(outside), str(life / "terms/2026-fall/courses/linked"))
    targets = find_targets(life, MONDAY)
    assert targets.courses == ("terms/2026-fall/courses/hist-205/README.md",)
    assert not any("linked" in path for path in snapshot(life, targets.editable))
