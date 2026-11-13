"""assignment_check.run: run_check with fake visits, claudes, notify, mail sender and board."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from mail_digest.assignment_check import CheckDeps, run_check
from mail_digest.assignment_check.check_config import load_check_config
from mail_digest.assignment_check.courses import CLASSROOM
from mail_digest.assignment_check.notices import BUSY
from mail_digest.assignment_check.visit import SiteVisit, VisitedPage
from mail_digest.claude import ClaudeRun

CONFIG = load_check_config(Path(__file__).with_name("check_config.toml"))
CLASSROOM_ACCOUNT = CONFIG.classroom_account
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone(timedelta(hours=-4)))
PLAN = "terms/2026-fall/weeks/2026-10-19-to-10-25/plan.md"
COURSE = "terms/2026-fall/courses/chem-120-general-chemistry/README.md"
OPEN_A18 = "- [ ] [chem-120] A18 (TODO: verify it was handed in)\n"
TICKED_A18 = "- [x] [chem-120] A18 (turned in per Classroom 2026-10-20) (site)\n"
CLASS = f"/u/1/c/{CONFIG.courses[-1].site_id}/a"
NAME = CONFIG.courses[-1].class_name


def _listing(name, item_id):
    """One Classroom to-do entry, as a snapshot shows it (DRAFT shape)."""
    url = f"{CLASS}/{item_id}/details"
    return f'- listitem "{NAME}":\n  - link "{name}":\n    - /url: {url}'


TEXTS = {
    "chem-120-turned-in": _listing("A18 Sorting", "ODk1MTIz"),
    "chem-120-not-turned-in": _listing("A19 Recursion", "ODk1MTI0"),
}
ITEMS = [
    {"page": "chem-120-turned-in", "name": "A18 Sorting", "ref": "ODk1MTIz", "due": ""},
    # Due yesterday and not turned in: overdue, so it's spoken.
    {
        "page": "chem-120-not-turned-in",
        "name": "A19 Recursion",
        "ref": "ODk1MTI0",
        "due": "2026-10-19",
    },
]


class FakeWorld:
    """A life/ folder, a state file, scripted visits and claudes, recording notify/mail/board."""

    def __init__(self, tmp_path: Path):
        self.life = tmp_path / "life"
        files = {
            "inbox.md": "# Inbox\n",
            PLAN: f"# Plan\n\n## CHEM 120\n{OPEN_A18}",
            COURSE: "# 315\n",
        }
        for relative, text in files.items():
            (self.life / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.life / relative).write_text(text, encoding="utf-8")
        self.tmp = tmp_path
        self.visit_status = {"classroom": "ok", "moodle": "ok"}
        self.visited, self.reads, self.writes = [], [], []
        self.spoken, self.emails, self.boards = [], [], []
        self.reader = ClaudeRun(result=_success(_reader_output()))
        self.edit = TICKED_A18  # what the fake writer puts in place of A18's open line

    def deps(self) -> CheckDeps:
        return CheckDeps(
            life_dir=self.life,
            state_path=self.tmp / "state.json",
            rejected_dir=self.tmp / "rejected",
            last_check_path=self.tmp / "last-check.json",
            config=CONFIG,
            visit=self._visit,
            read=lambda argv, context: self.reads.append(context) or self.reader,
            write=self._write,
            notify=lambda text: self.spoken.append(text) or True,
            send_email=lambda email: self.emails.append(email) or True,
            refresh_board=lambda: self.boards.append(True),
            now=lambda: NOW,
            find_claude=lambda: Path("claude.exe"),
            is_reviewed=lambda life_dir, path: True,
        )

    def _visit(self, site, pages):
        self.visited.append(site)
        if self.visit_status[site] != "ok":
            return SiteVisit(self.visit_status[site])
        # Moodle needs a login, as when the owner isn't at the PC; Classroom is read.
        if site != CLASSROOM:
            return SiteVisit("ok", tuple(VisitedPage(p.key, "login_needed") for p in pages))
        texts = {p.key: CLASSROOM_ACCOUNT + "\n" + TEXTS.get(p.key, "") for p in pages}
        return SiteVisit("ok", tuple(VisitedPage(p.key, "ok", texts[p.key]) for p in pages))

    def _write(self, argv, context):
        self.writes.append(context)
        plan = self.life / PLAN
        plan.write_text(plan.read_text(encoding="utf-8").replace(OPEN_A18, self.edit), "utf-8")
        return ClaudeRun(result=_success({"summary": "ticked A18"}))


def _success(output):
    return {"subtype": "success", "structured_output": output}


def _reader_output():
    keys = ["chem-120-not-turned-in", "chem-120-missing", "chem-120-turned-in"]
    items = [
        {"class_name": NAME, "kind": "assignment", "status_text": "", **item} for item in ITEMS
    ]
    return {
        "pages": [{"key": key, "readable": True, "account": CLASSROOM_ACCOUNT} for key in keys],
        "items": items,
        "suspicious": [],
    }


def test_a_busy_browser_starts_no_claude(tmp_path):
    world = FakeWorld(tmp_path)
    world.visit_status["classroom"] = "busy"
    assert run_check(world.deps()).exit_code == 1
    assert world.visited == ["classroom"]  # the Moodle launch never starts
    assert (world.reads, world.writes) == ([], [])
    assert world.spoken == [BUSY]


def test_a_failed_reader_starts_no_writer(tmp_path):
    world = FakeWorld(tmp_path)
    world.reader = ClaudeRun(error="lockdown check failed: tools are ['Bash']")
    assert run_check(world.deps()).exit_code == 1
    assert len(world.reads) == 1 and world.writes == []
    assert "Classroom reader failed" in world.spoken[0]


def test_a_guard_undo_speaks_no_items_and_sends_no_email(tmp_path):
    world = FakeWorld(tmp_path)
    world.edit = "- [x] [chem-120] A18 done, see https://evil.example (site)\n"
    run_check(world.deps())
    assert OPEN_A18 in (world.life / PLAN).read_text(encoding="utf-8")  # undone
    assert "A19" not in world.spoken[0] and "undid" in world.spoken[0]
    assert world.emails == []


def test_success_ticks_speaks_emails_and_refreshes_the_board(tmp_path):
    world = FakeWorld(tmp_path)
    outcome = run_check(world.deps())
    assert outcome.exit_code == 0
    # Moodle needed a login, so the writer is told; it got the one change (A18).
    assert "side-project: Moodle: login needed" in world.writes[0]
    assert TICKED_A18 in (world.life / PLAN).read_text(encoding="utf-8")
    [spoken] = world.spoken
    assert "Moodle needs you at the PC" in spoken and "A19 Recursion is overdue" in spoken
    assert spoken.endswith("Assignment check done: 1 update.")
    assert len(world.emails) == 1 and world.boards == [True]
    assert any("details" in line for line in outcome.lines)  # the links are printed
