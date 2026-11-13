"""Tests for mail_digest.mailbox: paged searches, completed accounts and the CLI client."""

import re
import sys
from datetime import datetime, timedelta, timezone

from mail_digest.mailbox import SEARCH_FAILED, AccountProblem, CliMailClient, gather_mail
from mail_digest.memory import Window

QUERY = re.compile(r"after:(\d+) before:(\d+)")
ZONE = timezone(timedelta(hours=-4))
START = 1_760_000_000


class FakeMail:
    """A mailbox per alias of {id: receive time}, searched newest first like Gmail, with
    dates to the minute like the mail tool. Deleted ids are listed but not returned."""

    def __init__(self, statuses, mailboxes, deleted=()):
        self.statuses = statuses
        self.mailboxes = mailboxes
        self.deleted = set(deleted)
        self.queries = []

    def accounts(self):
        return self.statuses

    def search(self, alias, query, max_results):
        self.queries.append(query)
        after, before = map(int, QUERY.fullmatch(query).groups())
        hits = sorted(
            ((t, i) for i, t in self.mailboxes[alias].items() if after <= t < before),
            reverse=True,
        )[:max_results]
        return [
            {"id": i, "date": datetime.fromtimestamp(t, ZONE).isoformat(timespec="minutes")}
            for t, i in hits
            if i not in self.deleted
        ]


def test_pages_back_by_date_until_every_message_is_found_once():
    # 200 messages 30 s apart, so pages share their oldest minute. Some were deleted
    # mid-search, so pages come back a little short of 50 but still mean "more".
    mailbox = {f"{n:04x}aaaa": START + 30 * n for n in range(200)}
    deleted = {f"{n:04x}aaaa" for n in range(5, 200, 40)}
    mail = FakeMail({"personal": "ok"}, {"personal": mailbox}, deleted)
    gathered = gather_mail(mail, {"personal": Window(START, START + 6000)})
    assert sorted(m["id"] for m in gathered.messages["personal"]) == sorted(set(mailbox) - deleted)
    assert gathered.completed == ("personal",)
    assert len(mail.queries) <= 6  # about one search per page, not a split tree


def test_only_ok_accounts_whose_searches_all_succeed_are_completed():
    mail = FakeMail(
        {"personal": "ok", "alt": "needs re-auth", "school": "ok"},
        # school has a full page inside one minute, so it can't page back past it.
        {"personal": {"0001aaaa": START}, "school": {f"{n:04x}bbbb": START for n in range(60)}},
    )
    windows = {alias: Window(START, START + 50) for alias in ("personal", "alt", "school", "work")}
    gathered = gather_mail(mail, windows)
    assert gathered.completed == ("personal",)
    assert list(gathered.messages) == ["personal"]
    # "work" isn't signed in at all: skipped quietly. school's failure is reported.
    assert gathered.problems == (
        AccountProblem("alt", "needs re-auth"),
        AccountProblem("school", SEARCH_FAILED),
    )


# A stand-in for the mail tool's CLI: real `mail accounts` rows, and search JSON with
# text a cp1252 console can't encode.
STAND_IN = r"""
import json, sys
if sys.argv[1] == "accounts":
    print(f"{'personal':<12} {'me@example.com':<32} ok")
    print(f"{'alt':<12} {'?':<32} needs re-auth  (odd (detail) ok error")
    print(f"{'school':<12} {'me@school.example.edu':<32} offline  (No network.)")
else:
    print(json.dumps([{"id": "18c2f3a4", "subject": "Café – due 😀"}], ensure_ascii=False))
"""


def test_cli_client_reads_the_mail_tools_real_output():
    # Regression: redirected output was cp1252, so non-ASCII mail failed or came back garbled.
    client = CliMailClient(command=(sys.executable, "-c", STAND_IN))
    assert client.accounts() == {"personal": "ok", "alt": "needs re-auth", "school": "offline"}
    [message] = client.search("personal", "after:1 before:2", 50)
    assert message["subject"] == "Café – due 😀"
