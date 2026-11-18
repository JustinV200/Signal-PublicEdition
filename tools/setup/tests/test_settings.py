"""Settings: the line writers keep comments, placeholders gate the step, schemas match examples."""

import json
import re
import shutil
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

from signal_setup import progress, registry, settings
from signal_setup.cli import agent, config
from signal_setup.cli.agent import AgentAsker
from signal_setup.settings.formats import for_path, psd1_lines, toml_lines
from signal_setup.steps import NEEDS_INPUT, run_step
from signal_setup.steps.settings_step import run as run_settings

REPO = Path(__file__).resolve().parents[3]
RepoFile = Callable[[str], Path]  # the conftest `repo_file` fixture

TOML = """# top comment
[a]
# the name
name = "old"  # trailing
items = [
    "x",  # one
    "y",
]
# hidden = 1

[b]
keep = true
"""


@pytest.mark.parametrize(
    ("key", "literal", "kept"),
    [
        ("a.name", '"new"', "# the name"),
        ("a.items", '["z"]', "keep = true"),
        ("a.hidden", "2", "# top comment"),
        ("b.added", '"v"', "[a]"),
        ("c.fresh", "3", "keep = true"),
    ],
)
def test_toml_writer_sets_one_key_and_keeps_the_rest(key: str, literal: str, kept: str) -> None:
    text = toml_lines.write(TOML, key, literal)
    table, _, name = key.rpartition(".")
    assert tomllib.loads(text)[table][name] == tomllib.loads(f"v = {literal}")["v"]
    assert kept in text
    assert len(tomllib.loads(text)["a"]) == len(tomllib.loads(TOML)["a"]) + (key == "a.hidden")


def test_psd1_writer_round_trips_arrays_and_numbers() -> None:
    text = "# c\n@{\n    RunTimes         = @('07:00')\n    TimeLimitMinutes = 45\n}\n"
    text = psd1_lines.write(text, "RunTimes", psd1_lines.literal(["06:30", "18:00"]))
    text = psd1_lines.write(text, "IntervalMinutes", psd1_lines.literal(5))
    assert psd1_lines.read(text, "RunTimes") == ["06:30", "18:00"]
    assert psd1_lines.read(text, "IntervalMinutes") == 5
    assert "    RunTimes         = @('06:30', '18:00')" in text and text.startswith("# c\n@{")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://lms.example.edu", True),
        ("you@school.example.com", True),
        (["ok.edu", "YOUR_COURSE_ID"], True),
        ("YOUR-TAG", True),
        ("<your city>", True),
        ("TODO(owner)", True),
        ("Signal whiteboard TODO sync", False),
        ("https://moodle.state.edu", False),
        (["a", "b"], False),
        (5, False),
    ],
)
def test_placeholder_patterns(value: object, expected: bool) -> None:
    assert settings.is_placeholder(value) is expected


def _checker_root(tmp_path: Path, repo_file: RepoFile) -> Path:
    """A repo copy with just the assignment checker's example configs."""
    for config_file in settings.load("mail-digest").files_in("checker"):
        (tmp_path / config_file.example).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo_file(config_file.example), tmp_path / config_file.example)
    return tmp_path


def test_markdown_scan_skips_template_slots_in_prose(tmp_path: Path) -> None:
    """Regression: the jobhunt runbook's prose bullets ("- Result: ... <message id> ...")
    read as placeholders left, so jobhunt's check never ran."""
    folder = tmp_path / "life/areas/job-search"
    folder.mkdir(parents=True)
    (folder / "profile.md").write_text("- Name: Sam\n", encoding="utf-8")
    (folder / "runbook.md").write_text(
        "- Applications per run: <a number>\n"
        "- Result: append `email <gmail message id> <subject>: verified` to its notes\n"
        "- Home city: <your city>, <your state>\n"
        "- Signature: Best, TODO(owner)\n",
        encoding="utf-8",
    )

    found = settings.leftovers(tmp_path, settings.load("jobhunt"), "")
    # AGENTS.md is Markdown too, but read with md_marked, so not in prose mode.
    assert not settings.is_prose_file("AGENTS.md")

    assert [s.id for s in found] == [
        "Applications per run",
        "life/areas/job-search/runbook.md:Home city",
        "life/areas/job-search/runbook.md:Signature",
    ]


def test_checker_step_needs_input_until_the_agent_sets_every_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], repo_file: RepoFile
) -> None:
    root, tool = _checker_root(tmp_path, repo_file), registry.by_id("mail-digest")
    data = progress.load(root)
    assert run_step(root, tool, tool.step("checker"), data, AgentAsker(None, None)) == NEEDS_INPUT
    assert "moodle.base" in settings.tool_leftovers(root, tool, data)

    pairs = [
        "moodle.base=https://moodle.state.edu",
        "moodle.courses=chem-120:42",
        "classroom.account=me@state.edu",
        "moodle.allow=moodle.state.edu, sso.state.edu",
        "moodle.login_host=sso.state.edu",
        "moodle.login_from_hosts=moodle.state.edu",
        "moodle.duo_code_relay_sites=sso.state.edu",
        "classroom.sso_host=sso.state.edu",
    ]
    assert config.set_settings(root, "mail-digest", pairs) == 0
    capsys.readouterr()
    assert config.set_settings(root, "mail-digest", ["classroom.school_domain=example.edu"]) == 1
    assert json.loads(capsys.readouterr().out)["placeholders_left"] == ["classroom.school_domain"]

    assert config.set_settings(root, "mail-digest", ["classroom.school_domain=state.edu"]) == 0
    data = progress.load(root)
    assert progress.step_status(data, "mail-digest", "checker") == progress.DONE
    assert settings.tool_leftovers(root, tool, data) == []
    written = (root / "tools/mail-digest/assignment-check.toml").read_text("utf-8")
    assert 'courses = ["chem-120:42"]' in written and "# Your school's Moodle address" in written


def test_mark_refuses_done_for_a_settings_step_with_placeholders_left(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], repo_file: RepoFile
) -> None:
    root, tool = _checker_root(tmp_path, repo_file), registry.by_id("mail-digest")
    run_step(root, tool, tool.step("checker"), progress.load(root), AgentAsker(None, None))
    capsys.readouterr()
    assert agent.mark(root, "mail-digest", "checker", progress.DONE) == 3
    assert "moodle.base" in json.loads(capsys.readouterr().out)["placeholders_left"]
    assert progress.step_status(progress.load(root), "mail-digest", "checker") != progress.DONE
    assert agent.mark(root, "mail-digest", "checker", progress.SKIPPED) == 0


@pytest.mark.parametrize(
    ("tool_id", "step_id", "missing"),
    [
        ("jobhunt", "settings", "life/areas/job-search/runbook.md: missing"),
        ("mail-digest", "checker", "tools/mail-digest/assignment-check.toml: missing"),
    ],
)
def test_mark_refuses_done_when_a_config_file_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], tool_id: str, step_id: str, missing: str
) -> None:
    """Regression: a never-created config file used to count as having no placeholders."""
    assert agent.mark(tmp_path, tool_id, step_id, progress.DONE) == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == NEEDS_INPUT and missing in out["placeholders_left"]
    assert progress.step_status(progress.load(tmp_path), tool_id, step_id) != progress.DONE


class _Typed:
    """A terminal-like asker that types the given answers in order (None = Enter)."""

    interactive = True

    def __init__(self, answers: list[str | None]) -> None:
        self.answers = answers

    def say(self, text: str) -> None:
        """Ignore output."""

    def confirm(self, question: str, default: bool) -> bool:
        """Always the default (no advanced settings)."""
        return default

    def text(self, question: str) -> str | None:
        """The next answer."""
        return self.answers.pop(0)


def test_changed_schedule_setting_reruns_a_done_schedule_step(tmp_path: Path) -> None:
    schedule = tmp_path / "tools/calendar/schedule/schedule.psd1"
    schedule.parent.mkdir(parents=True)
    shutil.copyfile(REPO / "tools/calendar/schedule/schedule.psd1", schedule)
    tool, data, reran = registry.by_id("calendar"), progress.load(tmp_path), []
    progress.set_step(data, "calendar", "schedule", progress.DONE)

    asker = _Typed(["often", "15"])  # a bad value is asked again
    status = run_settings(tmp_path, tool, tool.step("settings"), data, asker, reran.append)
    assert status == progress.DONE and [s.id for s in reran] == ["schedule"]
    assert "IntervalMinutes  = 15" in schedule.read_text("utf-8")


# One case per tool, so a tool whose files this checkout lacks skips alone.
@pytest.mark.parametrize("tool", registry.load(), ids=lambda tool: tool.id)
def test_every_schema_key_is_in_its_example(tool: registry.Tool, repo_file: RepoFile) -> None:
    """Guards drift: a renamed config key would silently stop being settable."""
    schema = settings.load(tool.id)
    steps = {s.group for s in tool.steps if s.kind == "settings"}
    assert (schema is None) == (not steps), tool.id
    for setting in schema.settings if schema else ():
        config_file = next(f for f in schema.files if f.path == setting.file)
        assert setting.group in steps, setting.id
        path = repo_file(config_file.example or config_file.path)
        text = path.read_text("utf-8")
        name = setting.key.rpartition(".")[2]
        commented = re.search(rf"^\s*#\s*{re.escape(name)}\s*=", text, re.M)
        assert for_path(path).read(text, setting.key) is not None or commented, setting.id


def test_context_handoff_threshold_rewrites_agents_md(tmp_path: Path, repo_file: RepoFile) -> None:
    shutil.copyfile(repo_file("AGENTS.md"), tmp_path / "AGENTS.md")
    setting = settings.find(tmp_path, settings.load("agents"), "context-handoff-percent")

    settings.set_value(tmp_path, setting, "60")
    with pytest.raises(ValueError, match="out of range"):
        settings.set_value(tmp_path, setting, "95")

    text = (tmp_path / "AGENTS.md").read_text("utf-8")
    assert "-->60<!-- /setting -->% of your context window" in text
    assert text.count("<!-- setting:") == 1  # nothing else in the file changed shape


def test_markdown_bool_setting_is_written_as_yes_or_no(tmp_path: Path, repo_file: RepoFile) -> None:
    """The runbook is prose the run reads: a bool is written yes/no and read back as a bool."""
    example = repo_file("tools/jobhunt/templates/runbook.example.md")
    runbook = tmp_path / "life/areas/job-search/runbook.md"
    runbook.parent.mkdir(parents=True)
    shutil.copyfile(example, runbook)
    setting = settings.find(tmp_path, settings.load("jobhunt"), "Tailor resume")

    settings.set_value(tmp_path, setting, "yes")
    assert "- Tailor resume: yes\n" in runbook.read_text("utf-8")
    assert settings.current(tmp_path, setting) is True  # read back as a bool, not "yes"
    settings.set_value(tmp_path, setting, "n")
    assert "- Tailor resume: no\n" in runbook.read_text("utf-8")
    assert settings.current(tmp_path, setting) is False
