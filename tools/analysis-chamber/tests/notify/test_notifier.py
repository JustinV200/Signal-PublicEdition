"""Tests for analysis_chamber.notify: the three channels, personal runs, failure isolation."""

from pathlib import Path

import pytest
from signal_hub_notify import HubNote

from analysis_chamber.config import load_config
from analysis_chamber.notify import Notifier
from analysis_chamber.notify.console_tasks import task_id
from analysis_chamber.runs import Manifest, Phase, Status

pytestmark = pytest.mark.asyncio

FINDING = "Revenue fell 12% after the price change"
REPORT = Path("life/analyses/2026-11-16-pricing/report.html")
RUN_ID = "2026-11-16-pricing"


class Fakes:
    """Records every channel call; a channel named in `broken` raises instead."""

    def __init__(self, broken: tuple[str, ...] = ()) -> None:
        self.commands: list[list[str]] = []
        self.entries: list = []
        self.notes: list[HubNote] = []
        self.broken = broken

    def run(self, argv: list[str], cwd: Path) -> None:
        if "console" in self.broken:
            raise RuntimeError("console down")
        self.commands.append(argv)

    def append(self, entry, now) -> None:
        if "brief" in self.broken:
            raise ValueError("brief down")
        self.entries.append(entry)

    async def deliver(self, note: HubNote) -> None:
        if "voice" in self.broken:
            raise RuntimeError("hub down")
        self.notes.append(note)


def make(fakes: Fakes) -> Notifier:
    return Notifier(load_config(Path("missing.toml")), fakes.run, fakes.append, fakes)


def manifest(personal: bool | None = False, **fields) -> Manifest:
    return Manifest(
        id=RUN_ID, question="Did the price change hurt revenue?", personal=personal, **fields
    )


async def test_progress_sets_task_and_debounces() -> None:
    fakes = Fakes()
    notifier = make(fakes)
    m = manifest(phase=Phase.ANALYSE, percent=40, status=Status.RUNNING)
    await notifier.progress(m)
    await notifier.progress(m)  # unchanged: skipped
    m.percent = 50
    await notifier.progress(m)
    assert len(fakes.commands) == 2
    argv = fakes.commands[0]
    assert argv[argv.index("set") + 1] == f"chamber-{RUN_ID}"
    assert argv[argv.index("--pct") + 1] == "40"
    assert argv[argv.index("--status") + 1] == "building"
    assert argv[argv.index("--next") + 1] == "analyse"


async def test_done_hits_all_three_channels() -> None:
    fakes = Fakes()
    await make(fakes).done(manifest(False), FINDING, REPORT)
    assert FINDING in fakes.entries[0].title
    assert str(REPORT) in fakes.entries[0].detail
    assert fakes.notes[0].text == f"Chamber run {RUN_ID} done, top finding: {FINDING}"
    assert fakes.commands[0][-2:] == ["done", f"chamber-{RUN_ID}"]


@pytest.mark.parametrize("personal", [True, None])
async def test_personal_run_leaks_no_finding(personal: bool | None) -> None:
    fakes = Fakes()
    await make(fakes).done(manifest(personal), FINDING, REPORT)
    text = fakes.entries[0].title + fakes.entries[0].detail + fakes.notes[0].text
    assert "Revenue" not in text
    assert RUN_ID in text


async def test_closed_only_removes_console_task() -> None:
    fakes = Fakes()
    await make(fakes).closed(manifest(status=Status.FAILED))
    assert len(fakes.commands) == 1
    assert fakes.commands[0][-2:] == ["rm", f"chamber-{RUN_ID}"]
    assert not fakes.entries
    assert not fakes.notes


@pytest.mark.parametrize("broken", ["console", "brief", "voice"])
async def test_one_channel_failing_does_not_stop_the_others(broken: str) -> None:
    fakes = Fakes(broken=(broken,))
    await make(fakes).done(manifest(False), FINDING, REPORT)
    sent = {"console": fakes.commands, "brief": fakes.entries, "voice": fakes.notes}
    assert all(calls for name, calls in sent.items() if name != broken)


async def test_long_run_ids_get_distinct_task_ids() -> None:
    first = task_id("2026-11-16-" + "a" * 40 + "-1")
    second = task_id("2026-11-16-" + "a" * 40 + "-2")
    assert first != second
    assert len(first) <= 40


async def test_personal_run_name_hides_question() -> None:
    fakes = Fakes()
    await make(fakes).progress(manifest(None, status=Status.RUNNING))
    argv = fakes.commands[0]
    assert argv[argv.index("--name") + 1] == "Chamber: personal run"
