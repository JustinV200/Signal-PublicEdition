"""Routine step 2 in code: which accounts to search, the paged search, and which completed.

The model used to do this through mail_accounts and mail_search. Now the runner does
it before claude starts and hands the model the messages it found, so the date math,
the paging and the completed-accounts list can't drift with the model.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from mail_digest.mailbox.client import OK_STATUS, MailClient, MailToolError
from mail_digest.memory import Window
from mail_digest.settings import MAX_SEARCHES_PER_ACCOUNT, SEARCH_PAGE_SIZE, SEARCH_PAGE_SLACK

log = logging.getLogger(__name__)

# The problem status of an ok account whose search failed or hit the search cap.
SEARCH_FAILED = "search failed"
# The mail tool's dates are to the minute, so a page's next one starts a minute later.
DATE_STEP_S = 60


@dataclass(frozen=True)
class AccountProblem:
    """A mail account the run couldn't search: alias and its `mail accounts` status,
    or SEARCH_FAILED."""

    alias: str
    status: str


@dataclass(frozen=True)
class GatheredMail:
    """What the runner found before claude starts.

    messages: each completed alias's messages in its window, deduplicated by id.
    completed: aliases whose every search succeeded (only these windows move forward).
    problems: aliases skipped because their status isn't ok, or whose search failed.
    """

    messages: dict[str, list[dict]]
    completed: tuple[str, ...]
    problems: tuple[AccountProblem, ...]


def gather_mail(client: MailClient, windows: dict[str, Window]) -> GatheredMail:
    """Search every ok account's window.

    An alias the mail tool doesn't list is skipped quietly. One that isn't ok is a
    problem. One whose search fails is a SEARCH_FAILED problem (spoken weekly) with
    none of its messages, so its window stays put and the next run fetches it again.
    Raises MailToolError if the accounts can't be listed at all.
    """
    statuses = client.accounts()
    messages, completed, problems = {}, [], []
    for alias, window in windows.items():
        status = statuses.get(alias)
        if status is None:
            log.info("%s isn't signed in to the mail tool; skipping it", alias)
            continue
        if status != OK_STATUS:
            problems.append(AccountProblem(alias, status))
            continue
        try:
            messages[alias] = search_window(client, alias, window)
        except MailToolError as error:
            log.warning("%s: search failed, retrying it next run: %s", alias, error)
            problems.append(AccountProblem(alias, SEARCH_FAILED))
            continue
        completed.append(alias)
    return GatheredMail(messages, tuple(completed), tuple(problems))


def search_window(client: MailClient, alias: str, window: Window) -> list[dict]:
    """Every message in window, a page at a time from the newest back.

    While a page comes back at or near SEARCH_PAGE_SIZE (the mail tool drops messages
    deleted mid-search, so a short page may still mean more), the next search ends a
    minute after the oldest date on it. Pages overlap by that minute, and messages are
    kept once by id. Raises MailToolError if a search fails, a full page can't move
    back (no dates, or a page's worth in one minute), or the account needs more than
    MAX_SEARCHES_PER_ACCOUNT searches.
    """
    found: dict[str, dict] = {}
    before = window.before
    for _ in range(MAX_SEARCHES_PER_ACCOUNT):
        page = client.search(alias, f"after:{window.after} before:{before}", SEARCH_PAGE_SIZE)
        for message in page:
            found.setdefault(message["id"], message)
        if len(page) < SEARCH_PAGE_SIZE - SEARCH_PAGE_SLACK:
            return list(found.values())
        next_before = _oldest_s(page) + DATE_STEP_S
        if next_before >= before:
            raise MailToolError(f"a page of mail before {before} can't be paged past")
        before = next_before
    raise MailToolError(f"more than {MAX_SEARCHES_PER_ACCOUNT} searches needed")


def _oldest_s(page: list[dict]) -> int:
    """The Unix time of the oldest message date on page. Raises MailToolError if none parse."""
    stamps = []
    for message in page:
        try:
            stamps.append(int(datetime.fromisoformat(str(message.get("date"))).timestamp()))
        except ValueError:
            continue  # a message with no date can't move the page back; the rest can
    if not stamps:
        raise MailToolError("no message on a full page has a date")
    return min(stamps)
