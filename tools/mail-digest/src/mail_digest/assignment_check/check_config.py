"""Load and check the owner's assignment-check.toml into a CheckConfig.

The file is gitignored; setup copies it from assignment-check.example.toml and asks
for every value. It is checked here, at the boundary, so a typo can't turn into a
visit to the wrong host: bases must be https with no path beyond Classroom's /u/N
slot, tags and ids must be plain tokens, and a Classroom course needs its class name.
"""

import re
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from mail_digest.assignment_check.courses import CLASSROOM, MOODLE, CheckConfig, Course

# A life/ course tag ("chem-120") and a site's course id (Moodle's ?id=, Classroom's id).
TAG = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")
SITE_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
# The only path a base may have: none, or Classroom's account slot.
BASE_PATH = re.compile(r"(/u/[0-9])?")
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class CheckConfigError(ValueError):
    """The config file is missing, isn't TOML, or has a bad value (the message says which)."""


def load_check_config(path: Path) -> CheckConfig:
    """Read path into a CheckConfig. Raises CheckConfigError (missing file or bad value)."""
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CheckConfigError(f"{path.name} not found: run `setup mail-digest`") from error
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CheckConfigError(f"can't read {path.name}: {error}") from error
    moodle, classroom = _table(data, MOODLE), _table(data, CLASSROOM)
    courses = tuple(_course(MOODLE, entry) for entry in _list(moodle, "courses")) + tuple(
        _course(CLASSROOM, entry) for entry in _list(classroom, "courses")
    )
    sites = {course.site for course in courses}
    account = str(classroom.get("account", ""))
    if CLASSROOM in sites and not EMAIL.fullmatch(account):
        raise CheckConfigError("[classroom] account must be the school Google account's email")
    return CheckConfig(
        moodle_base=_base(moodle.get("base", ""), "[moodle] base", MOODLE in sites),
        classroom_base=_base(classroom.get("base", ""), "[classroom] base", CLASSROOM in sites),
        classroom_account=account.casefold(),
        courses=courses,
    )


def _table(data: dict, name: str) -> dict:
    """data[name] as a table ({} if absent)."""
    table = data.get(name, {})
    if not isinstance(table, dict):
        raise CheckConfigError(f"[{name}] must be a table")
    return table


def _list(table: dict, name: str) -> list[str]:
    """table[name] as a list of strings ([] if absent)."""
    entries = table.get(name, [])
    if not isinstance(entries, list) or not all(isinstance(e, str) for e in entries):
        raise CheckConfigError(f"{name} must be a list of strings")
    return entries


def _base(value: object, label: str, is_used: bool) -> str:
    """An https base URL with no query, fragment or trailing slash ("" for an unused site)."""
    if not is_used:
        return ""
    parts = urlsplit(str(value))
    is_ok = (
        parts.scheme == "https"
        and parts.hostname is not None
        and parts.port is None
        and not (parts.query or parts.fragment or parts.username)
        and BASE_PATH.fullmatch(parts.path)
    )
    if not is_ok:
        raise CheckConfigError(f"{label} must be an https address like https://lms.school.edu")
    return f"https://{parts.hostname}{parts.path}"


def _course(site: str, entry: str) -> Course:
    """One "tag:id" (Moodle) or "tag:id:class name" (Classroom) entry, checked."""
    tag, _, rest = entry.partition(":")
    site_id, _, class_name = rest.partition(":")
    if not TAG.fullmatch(tag):
        raise CheckConfigError(f"course tag {tag!r} must be lowercase letters, digits and -")
    if not SITE_ID.fullmatch(site_id):
        raise CheckConfigError(f"course {tag}: id must be letters, digits, _ or -")
    if site == CLASSROOM and not class_name.strip():
        raise CheckConfigError(f"course {tag}: a Classroom course needs its class name")
    return Course(tag, site, site_id, class_name=class_name.strip())
