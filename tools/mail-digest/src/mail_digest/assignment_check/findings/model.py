"""What the checks produce: validated items, the problems that stopped a course being read.

Every field of an Item was either checked against the visit's own page text or set by
the runner (status, link, flags), so it's what the writer and the announcements get.
"""

from dataclasses import dataclass

# An item's status, set by the runner from where the item was listed, never the model.
DONE = "done"  # turned in or submitted for grading
OPEN = "open"  # assigned, not submitted
MISSING = "missing"  # Classroom's missing list: past due, not turned in
UNKNOWN = "unknown"  # no status the runner trusts; it changes nothing

# Why a page, and so its course, wasn't used.
LOGIN_NEEDED = "login_needed"
GOOGLE_SIGNIN_NEEDED = "google_signin_needed"
PAGE_ERROR = "error"
UNREADABLE = "unreadable"
WRONG_ACCOUNT = "wrong_account"
SUSPICIOUS = "suspicious"


@dataclass(frozen=True)
class Item:
    """One validated assignment, quiz or event.

    course: the course tag from courses.py. due: "YYYY-MM-DD HH:MM", "YYYY-MM-DD"
    or "". link: built by the runner from the page's own URLs (never goes in life/).
    overdue / due_soon: worked out by the runner from due and status.
    """

    course: str
    site: str
    name: str
    kind: str
    due: str
    status: str
    link: str
    overdue: bool = False
    due_soon: bool = False


@dataclass(frozen=True)
class Problem:
    """A page that couldn't be used, so its whole course is left alone this check."""

    course: str
    site: str
    page: str
    reason: str


@dataclass(frozen=True)
class Findings:
    """One check's validated items and its page problems."""

    items: tuple[Item, ...] = ()
    problems: tuple[Problem, ...] = ()


def fold(text: str) -> str:
    """text with whitespace runs made one space, casefolded, for "occurs in the page" checks."""
    return " ".join(text.split()).casefold()
