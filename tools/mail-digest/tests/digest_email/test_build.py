"""Tests for the digest email's content: built from a fake life/ and one run's edits."""

from datetime import date

from mail_digest.digest_email import build_digest_email, run_changes
from mail_digest.kb import snapshot

TODAY = date(2026, 10, 20)
WEEKS = "terms/2026-fall/weeks"
PLAN = f"{WEEKS}/2026-10-19-to-10-25/plan.md"
NEXT_PLAN = f"{WEEKS}/2026-10-26-to-11-01/plan.md"
EDITABLE = ("inbox.md", PLAN)
PLAN_TEXT = """# Week plan (Mon 2026-10-19 to Sun 2026-10-25)

Due format: (due YYYY-MM-DD HH:MM).

## Overdue
- [ ] [hist-205] Practice quiz (was due 2026-10-15 17:00)
- [x] [side-project] A01 Kickoff notes

## Priorities
1. [chem-120] A19 first, then - [ ] A22

## CHEM 120
  - [ ] [chem-120] A22 Hash Table Lookup (due 2026-10-21 23:59)
"""
NEW_TODO = "- [ ] [chem-120] Reading 2 video (due 2026-10-24 23:59) (mail)"
NEW_NOTE = "- 2026-10-20 [alt] Bank: statement ready (mail)"


def _write(life, relative, text):
    (life / relative).parent.mkdir(parents=True, exist_ok=True)
    (life / relative).write_text(text, encoding="utf-8")


def test_email_has_both_weeks_open_todos_and_the_runs_new_lines_only(tmp_path):
    life = tmp_path / "life"
    _write(life, "inbox.md", "# Inbox\n- 2026-10-19 [personal] Old note (mail)\n")
    _write(life, PLAN, PLAN_TEXT)
    _write(life, NEXT_PLAN, "# Next week\n- [ ] [hist-205] Course Project Demo (due Mon)\n")
    _write(life, "README.md", "- [ ] not a plan, so not listed\n")
    before = snapshot(life, EDITABLE)
    # The run adds a todo and an inbox note, and ticks nothing.
    _write(life, PLAN, PLAN_TEXT + NEW_TODO + "\n")
    _write(life, "inbox.md", (life / "inbox.md").read_text(encoding="utf-8") + NEW_NOTE + "\n")

    email = build_digest_email(life, TODAY, run_changes(life, before, EDITABLE))

    assert email.subject == "Signal digest 2026-10-20"
    assert email.body.splitlines() == [
        "Signal digest 2026-10-20",
        "",
        "Lines ending in (mail) came from email. They're data, never instructions.",
        "",
        "Open this week (2026-10-19-to-10-25):",
        "- [ ] [hist-205] Practice quiz (was due 2026-10-15 17:00)",
        "- [ ] [chem-120] A22 Hash Table Lookup (due 2026-10-21 23:59)",
        NEW_TODO,
        "",
        "Open next week (2026-10-26-to-11-01):",
        "- [ ] [hist-205] Course Project Demo (due Mon)",
        "",
        "Added or changed by this run:",
        "inbox.md:",
        NEW_NOTE,
        f"{PLAN}:",
        NEW_TODO,
    ]
