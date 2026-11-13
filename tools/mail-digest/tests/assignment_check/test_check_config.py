"""assignment_check.check_config: a bad value in the owner's config never reaches a visit."""

from pathlib import Path

import pytest

from mail_digest.assignment_check.check_config import CheckConfigError, load_check_config

GOOD_COURSE = 'courses = ["chem-120:42"]\n'


def _write(tmp_path: Path, moodle_base: str, extra: str = GOOD_COURSE) -> Path:
    path = tmp_path / "assignment-check.toml"
    path.write_text(f'[moodle]\nbase = "{moodle_base}"\n{extra}', encoding="utf-8")
    return path


def test_a_good_config_builds_the_pages_base(tmp_path):
    config = load_check_config(_write(tmp_path, "https://LMS.school.edu"))
    assert config.moodle_base == "https://lms.school.edu"
    assert [c.tag for c in config.courses] == ["chem-120"]


@pytest.mark.parametrize(
    ("base", "extra"),
    [
        ("http://lms.school.edu", GOOD_COURSE),
        ("https://lms.school.edu:8443", GOOD_COURSE),
        ("https://user@lms.school.edu", GOOD_COURSE),
        ("https://lms.school.edu/evil?x=1", GOOD_COURSE),
        ("https://lms.school.edu", GOOD_COURSE.replace("42", "42/../x")),
        ("https://lms.school.edu", GOOD_COURSE.replace("chem-120", "CHEM 120")),
        ("https://lms.school.edu", '[classroom]\ncourses = ["chem-120:Q2xh:Chem"]\n'),  # no account
        (
            "https://lms.school.edu",
            '[classroom]\naccount = "a@b.edu"\ncourses = ["chem-120:Q2xh"]\n',
        ),
    ],
    ids=["http", "port", "userinfo", "path", "id-path", "tag", "no-account", "no-class-name"],
)
def test_a_bad_value_is_refused(tmp_path, base, extra):
    with pytest.raises(CheckConfigError):
        load_check_config(_write(tmp_path, base, extra))


def test_a_missing_file_says_to_run_setup(tmp_path):
    with pytest.raises(CheckConfigError, match="setup"):
        load_check_config(tmp_path / "nope.toml")
