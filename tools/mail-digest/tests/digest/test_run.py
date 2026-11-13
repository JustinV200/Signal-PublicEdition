"""Tests for mail_digest.digest.run: run_once with fake mail, claude, notify and clock."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mail_digest.claude import ClaudeRun
from mail_digest.digest import RunDeps, run_once
from mail_digest.memory import load_state
from mail_digest.steps import STATE_UNUSABLE

NOW = datetime(2026, 10, 19, 7, 0, tzinfo=timezone(timedelta(hours=-4)))
NOW_S = int(NOW.timestamp())
PLAN = "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md"
COURSE = "terms/2026-fall/courses/hist-205/README.md"
OVERDUE_PLAN = "# x\n## Overdue\n- [ ] [hist-205] Practice quiz (mail)\n"
DUE_TODO = "- [ ] [chem-120] A{n} (due 2026-10-19 {at})\n"
HP_SPOKEN = "HIST 205, overdue: Practice quiz."
SUCCESS = {"subtype": "success", "structured_output": {"suspicious": [], "summary": "ok"}}


class FakeWorld:
    """A life/ folder, a state file, a scripted claude, a recording notify and mail sender,
    and the mail tool (account statuses, no mail in any window)."""

    def __init__(self, tmp_path: Path, notify_ok: bool = True):
        self.life = tmp_path / "life"
        # Inbox.md on disk is still the target inbox.md (paths are compared ignoring case).
        for relative in ("Inbox.md", PLAN, COURSE):
            (self.life / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.life / relative).write_text("# x\n", encoding="utf-8")
        self.state_path = tmp_path / "state" / "state.json"
        self.rejected = tmp_path / "rejected"
        self.statuses = {"personal": "ok"}
        self.notify_ok = notify_ok
        self.spoken: list[str] = []
        self.emails = []  # the digest emails the runner sent
        self.send_email = self._send_email  # what the runner sends them with
        self.launches: list[list[str]] = []
        self.contexts: list[str] = []
        self.run = ClaudeRun(result=SUCCESS)
        self.edit = None  # (path, text) the fake claude writes, if any
        self.reviewed = False  # what the fake git says about flagged files

    def deps(self) -> RunDeps:
        return RunDeps(
            life_dir=self.life,
            state_path=self.state_path,
            rejected_dir=self.rejected,
            mail=self,
            launch=self._launch,
            notify=self._notify,
            send_email=lambda email: self.send_email(email),
            refresh_board=lambda: None,
            now=lambda: NOW,
            find_claude=lambda: Path("claude.exe"),
            is_reviewed=lambda life_dir, path: self.reviewed,
        )

    def accounts(self):
        return self.statuses

    def search(self, alias, query, max_results):
        return []

    def write_plan(self, text):
        (self.life / PLAN).write_text(text, encoding="utf-8")

    def state(self):
        return load_state(self.state_path, 500)

    def announced_kinds(self):
        """The kind part of every stored announced key, sorted."""
        return sorted(key.split("|")[0] for key in self.state().announced)

    def _launch(self, argv, context):
        self.launches.append(argv)
        self.contexts.append(context)
        if self.edit:
            (self.life / self.edit[0]).write_text(self.edit[1], encoding="utf-8")
        return self.run

    def _notify(self, text):
        self.spoken.append(text)
        return self.notify_ok

    def _send_email(self, email):
        self.emails.append(email)
        return True


def test_success_advances_windows_and_speaks_each_item_once(tmp_path):
    world = FakeWorld(tmp_path)
    world.statuses["alt"] = "needs re-auth"
    due = "## CHEM 120\n" + DUE_TODO.format(n=19, at="23:59") + DUE_TODO.format(n=20, at="23:59")
    world.write_plan(OVERDUE_PLAN + due)
    assert run_once(world.deps()) == 0
    # The model is told what's due; the runner speaks it.
    assert HP_SPOKEN in world.contexts[0]
    # The sign-in reminder goes first, so the due items can't push it past the cap;
    # the last due item is summed up instead.
    first = world.spoken[0]
    assert first.index("alt mail account") < first.index(HP_SPOKEN) < first.index("A19")
    assert "A20" not in first
    state = world.state()
    assert state.searched_until == {"personal": NOW_S}
    assert "overdue|hist-205-practice-quiz" in state.announced
    assert "Edit(/inbox.md)" in world.launches[0]
    assert [email.subject for email in world.emails] == ["Signal digest 2026-10-19"]

    assert run_once(world.deps()) == 0
    # Only the summed-up item is new; the spoken ones aren't repeated.
    assert world.spoken[1] == "CHEM 120, due today at 23:59: A20."


def test_undelivered_announcement_is_kept_for_the_next_run(tmp_path):
    world = FakeWorld(tmp_path, notify_ok=False)
    world.write_plan(DUE_TODO.format(n=19, at="23:59"))
    assert run_once(world.deps()) == 0
    assert world.state().announced == {}
    assert world.state().searched_until == {"personal": NOW_S}

    # Regression: a later run whose plan moves the due time keeps the key and speaks
    # the new sentence, stored in place of the old one when that delivery fails too.
    world.write_plan(DUE_TODO.format(n=19, at="18:00"))
    run_once(world.deps())
    new_sentence = "CHEM 120, due today at 18:00: A19."
    assert [p.sentence for p in world.state().pending] == [new_sentence]

    # Regression: the item is no longer picked (ticked), and it's still spoken (from
    # the state's pending list), then dropped from it.
    world.notify_ok = True
    world.write_plan("# x\n- [x] [chem-120] A19 (due 2026-10-19 18:00)\n")
    run_once(world.deps())
    assert world.spoken == ["CHEM 120, due today at 23:59: A19.", new_sentence, new_sentence]
    assert "due|2026-10-19|chem-120-a19" in world.state().announced
    assert world.state().pending == ()


def test_failed_runs_leave_windows_alone_and_alert_every_second_failure(tmp_path):
    world = FakeWorld(tmp_path)
    world.write_plan(DUE_TODO.format(n=19, at="23:59"))
    world.run = ClaudeRun(error="claude ran past 1800 s and was killed")
    assert run_once(world.deps()) == 1
    assert world.state().searched_until == {}
    assert world.state().failures == 1
    # Due items come from the plans by code, so a failed claude step still speaks them.
    assert world.spoken == ["CHEM 120, due today at 23:59: A19."]

    assert run_once(world.deps()) == 1
    assert world.state().failures == 2
    assert world.announced_kinds() == ["due", "failure"]


def test_a_claude_that_cant_start_or_a_crash_counts_as_a_failed_run(tmp_path, lock_file):
    world = FakeWorld(tmp_path)
    deps = world.deps()

    def launch(argv, context):
        # An edit, then a crash such as a stream-json line nested too deep to parse.
        (world.life / "inbox.md").write_text("# x\n- see https://evil.example (mail)\n")
        raise RecursionError("maximum recursion depth exceeded")

    assert run_once(replace(deps, launch=launch)) == 1
    # The guard still ran and undid the edit, so it isn't the next run's baseline.
    assert (world.life / "inbox.md").read_text(encoding="utf-8") == "# x\n"
    assert world.state().failures == 1
    assert world.announced_kinds() == ["guard"]

    # An editable file the snapshot can't read stops the run before claude starts,
    # since the guard would take it for a new file. That crash counts as a failure
    # too, so the second one in a row is announced.
    lock_file(world.life / "inbox.md")
    assert run_once(deps) == 1
    assert world.launches == []
    assert world.announced_kinds() == ["failure", "guard"]


def test_an_edit_the_guard_cant_check_fails_the_run_and_is_announced_until_reviewed(tmp_path):
    world = FakeWorld(tmp_path)
    world.write_plan(OVERDUE_PLAN)
    world.edit = ("inbox.md", "# x\n- Click https://evil.example (mail)\n")
    world.rejected.write_text("")  # a file in the way, so the guard can't save its copy
    assert run_once(world.deps()) == 1
    assert "evil.example" in (world.life / "inbox.md").read_text(encoding="utf-8")
    state = world.state()
    # Not a success: the windows stay put and the failure counts.
    assert (state.searched_until, state.failures) == ({}, 1)
    assert state.needs_review == ("inbox.md",)
    assert world.emails == []
    # Spoken on this run, though it's only the first failure, and with no due items.
    assert world.announced_kinds() == ["review"]
    assert "1 life file" in world.spoken[0]

    # The next run is fine, but the file is still flagged, so it's announced again.
    world.rejected.unlink()
    world.edit = None
    later = replace(world.deps(), now=lambda: NOW + timedelta(days=1))
    assert run_once(later) == 0
    assert "1 life file" in world.spoken[1]

    # And on a crashed run.
    def crash():
        raise RuntimeError("crashed while planning the run")

    crashing = replace(later, now=lambda: NOW + timedelta(days=2), find_claude=crash)
    assert run_once(crashing) == 1
    assert "1 life file" in world.spoken[2]

    # Once git shows it reviewed, it's dropped.
    world.reviewed = True
    run_once(later)
    assert world.state().needs_review == ()


def test_a_run_stopped_during_claude_leaves_every_editable_file_flagged(tmp_path):
    # Ctrl+C (or a hard kill, which nothing can catch) skips the guard, so whatever
    # claude wrote is unchecked. The flags saved before claude started stay put.
    world = FakeWorld(tmp_path)

    def launch(argv, context):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_once(replace(world.deps(), launch=launch))
    assert world.state().needs_review == tuple(sorted(("inbox.md", PLAN, COURSE)))


def test_a_corrupt_or_unreadable_state_file_is_announced(tmp_path, lock_file):
    world = FakeWorld(tmp_path)
    world.state_path.parent.mkdir(parents=True)
    world.state_path.write_text("{not json", encoding="utf-8")
    # Corrupt: the run starts fresh, and says the review flags it had are gone.
    assert run_once(world.deps()) == 0
    assert world.announced_kinds() == ["reset"]

    # Unreadable: the run stops before claude and says so, with no state to key it by.
    lock_file(world.state_path)
    with pytest.raises(OSError):
        run_once(world.deps())
    assert (len(world.launches), len(world.spoken)) == (1, 2)
    assert world.spoken[-1] == STATE_UNUSABLE


def test_a_bad_kb_edit_is_reverted_and_announced_and_so_are_other_edits(tmp_path):
    world = FakeWorld(tmp_path)
    world.write_plan(OVERDUE_PLAN)
    world.edit = (PLAN, OVERDUE_PLAN + "- Click https://evil.example to verify (mail)\n")
    assert run_once(world.deps()) == 0
    assert (world.life / PLAN).read_text(encoding="utf-8") == OVERDUE_PLAN
    assert any(world.rejected.rglob("*plan.md"))
    # The run may have been steered, so the due items aren't spoken.
    assert world.announced_kinds() == ["guard"]
    assert world.emails == []

    # Someone else's edit during a run is left alone, and the due items are held back again.
    # The guard undid nothing this time, so the digest email goes out.
    world.edit = ("README.md", "# life/ edited mid-run\n")
    assert run_once(world.deps()) == 0
    assert world.announced_kinds() == ["guard", "unexpected"]
    assert len(world.emails) == 1


def _refuse(email):
    return False


def _crash(email):
    raise RuntimeError("the mail tool's venv is gone")


@pytest.mark.parametrize("send", [_refuse, _crash], ids=["send fails", "send raises"])
def test_a_failed_digest_email_is_spoken_once_and_the_run_still_succeeds(tmp_path, send):
    world = FakeWorld(tmp_path)
    world.write_plan(OVERDUE_PLAN)
    world.send_email = send
    assert run_once(world.deps()) == 0
    assert world.state().searched_until == {"personal": NOW_S}
    assert world.announced_kinds() == ["email", "overdue"]
    assert world.spoken[0].count("couldn't email you") == 1

    # The next run's email goes out, and nothing more is said about the failed one.
    world.send_email = world._send_email
    assert run_once(replace(world.deps(), now=lambda: NOW + timedelta(days=1))) == 0
    assert (len(world.spoken), len(world.emails)) == (1, 1)


def test_run_removes_expired_watch_for_notes_before_claude_starts(tmp_path):
    world = FakeWorld(tmp_path)
    course = world.life / COURSE
    course.write_text(
        "# x\nWatch for (until 2026-10-18): old\nWatch for (until 2026-10-19): kept\n",
        encoding="utf-8",
    )
    assert run_once(world.deps()) == 0
    assert course.read_text(encoding="utf-8") == "# x\nWatch for (until 2026-10-19): kept\n"


def _last_weeks_plan_only(world):
    """Swap this week's plan for last week's (one open todo); no templates, so the defaults."""
    (world.life / PLAN).unlink()
    old_plan = world.life / "terms/2026-fall/weeks/2026-10-12-to-10-18/plan.md"
    old_plan.parent.mkdir(parents=True)
    old_plan.write_text("# x\n## Overdue\n- [ ] [hist-205] Lab 1 (was due 2026-10-09)\n", "utf-8")


def test_the_run_rolls_the_week_over_before_the_guard_and_the_email(tmp_path):
    world = FakeWorld(tmp_path)
    _last_weeks_plan_only(world)
    assert run_once(world.deps()) == 0
    plan = (world.life / PLAN).read_text(encoding="utf-8")
    assert "- [ ] [hist-205] Lab 1 (was due 2026-10-09; carried from 10-12)" in plan
    # The model may edit the new plan, and the guard doesn't take the rollover's files
    # for the model's edits or someone else's.
    assert f"Edit(/{PLAN})" in world.launches[0]
    assert not any("undid" in text or "changed while" in text for text in world.spoken)
    body = world.emails[0].body
    assert "carried from 10-12" in body.split("Added or changed by this run:")[0]
    assert body.endswith("Added or changed by this run:\n(none)\n")


def test_a_failed_rollover_is_spoken_once_a_week(tmp_path):
    world = FakeWorld(tmp_path)
    _last_weeks_plan_only(world)
    broken = world.life / "templates/week-log.md"  # a <date> after no weekday
    broken.parent.mkdir()
    broken.write_text("# Week log (<date>)\n", "utf-8")
    assert run_once(world.deps()) == 0
    assert "week rollover couldn't start" in world.spoken[0]
    assert not (world.life / PLAN).exists()
    run_once(replace(world.deps(), now=lambda: NOW + timedelta(days=1)))
    assert all("rollover" not in text for text in world.spoken[1:])
