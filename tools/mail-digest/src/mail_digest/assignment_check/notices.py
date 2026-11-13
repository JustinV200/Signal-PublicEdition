"""What a check says out loud. The runner writes every sentence; none come from the model.

In order (design section 7): the runner's notices (a login or Google sign-in needed,
pages that couldn't be read, were on the wrong account or were suspicious), then v1's
kb_alerts, then the items (newly overdue and not done, then due within 24 hours and
not done), and always a closing line, since the owner is waiting: the done line, or
why the check stopped. Notices are keyed by run, so they're spoken every check that
has them; items are keyed by course and name, so each is spoken once in 30 days.
"""

from mail_digest.announce import Announcement
from mail_digest.assignment_check.courses import MOODLE, SITE_NAMES
from mail_digest.assignment_check.findings import (
    GOOGLE_SIGNIN_NEEDED,
    LOGIN_NEEDED,
    PAGE_ERROR,
    SUSPICIOUS,
    UNREADABLE,
    WRONG_ACCOUNT,
    Item,
    Problem,
)
from mail_digest.claude import clean_sentence, slugify

CHECK_NAME = "assignment check"
BUSY = "The checker's browser is open. Close it and ask again."
MOODLE_LOGIN = "Moodle needs you at the PC to log in. Ask again when you're there."
GOOGLE_SIGNIN = (
    "Classroom needs a Google sign-in on the checker's browser. Sign in by hand in a "
    "normal browser window, then ask again."
)
CRASHED = "The assignment check crashed. Check its log."
UNREAD_REASONS = (PAGE_ERROR, UNREADABLE)


def stopped_line(why: str) -> str:
    """The closing line of a check that stopped before the writer (why: a short clause)."""
    return f"The assignment check stopped: {why}. Check its log."


def problem_notices(problems: tuple[Problem, ...], run_start: int) -> list[Announcement]:
    """One notice per kind of page problem this check had."""
    reasons = {(problem.site, problem.reason) for problem in problems}
    notices = []
    if (MOODLE, LOGIN_NEEDED) in reasons:
        notices.append(Announcement(f"login|{run_start}", MOODLE_LOGIN))
    if any(reason == GOOGLE_SIGNIN_NEEDED for _site, reason in reasons):
        notices.append(Announcement(f"signin|{run_start}", GOOGLE_SIGNIN))
    for site in sorted({site for site, reason in reasons if reason == WRONG_ACCOUNT}):
        sentence = f"{SITE_NAMES[site]} showed the wrong Google account, so it was skipped."
        notices.append(Announcement(f"account|{site}|{run_start}", sentence))
    for site in sorted({site for site, reason in reasons if reason == SUSPICIOUS}):
        sentence = f"A {SITE_NAMES[site]} page had text aimed at an assistant. Check the log."
        notices.append(Announcement(f"suspect|{site}|{run_start}", sentence))
    unread = sorted({SITE_NAMES[site] for site, reason in reasons if reason in UNREAD_REASONS})
    if unread:
        sentence = f"Some {' and '.join(unread)} pages couldn't be read this time."
        notices.append(Announcement(f"unread|{run_start}", sentence))
    return notices


def item_notices(items: tuple[Item, ...]) -> list[Announcement]:
    """The items to speak: overdue ones first, then those due within 24 hours."""
    overdue = [_item_notice("overdue", item, "is overdue") for item in items if item.overdue]
    soon = [_item_notice("due", item, "is due within a day") for item in items if item.due_soon]
    return [notice for notice in (*overdue, *soon) if notice is not None]


def done_line(updates: int, waiting: int) -> str:
    """The closing line of a check that got through: its updates, and how many wait."""
    line = f"Assignment check done: {_count(updates, 'update') if updates else 'nothing new'}."
    return f"{line} {_count(waiting, 'more update')} next check." if waiting else line


def _count(number: int, noun: str) -> str:
    """ "1 update", "3 updates"."""
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _item_notice(kind: str, item: Item, what: str) -> Announcement | None:
    """One item's notice, keyed "<kind>|<course>-<name slug>", or None if nothing's speakable."""
    slug = slugify(f"{item.course} {item.name}")
    sentence = clean_sentence(f"{_spoken_course(item.course)}: {item.name} {what}.")
    return Announcement(f"{kind}|{slug}", sentence) if slug and sentence else None


def _spoken_course(tag: str) -> str:
    """A course tag as it's said: "chem-120" as "CHEM 120", "side-project" as "Side project"."""
    words = tag.split("-")
    if words[-1].isdigit():
        return " ".join(word.upper() for word in words)
    return " ".join(words).capitalize()
