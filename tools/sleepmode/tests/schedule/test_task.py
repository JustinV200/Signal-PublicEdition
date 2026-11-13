"""Tests for the wake task's XML and schtasks calls, on a fake runner (no task is registered)."""

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from sleepmode.schedule import ScheduleError, WakeScheduler, WakeTask, task_xml
from sleepmode.schedule.task import SCHTASKS

WAKE = datetime(2026, 10, 20, 7, 0)
TASK = WakeTask(
    name="Signal sleep mode wake",
    command=Path(r"C:\src\Signal\tools\sleepmode\.venv\Scripts\pythonw.exe"),
    arguments="-m sleepmode wake --reason schedule",
    working_dir=Path(r"C:\src\Signal\tools\sleepmode"),
    time_limit="PT5M",
)


class FakeSchtasks:
    """Records schtasks calls, keeps a copy of any XML file passed, and answers by verb."""

    def __init__(self, exit_codes: dict[str, int] | None = None) -> None:
        self.calls: list[list[str]] = []
        self.xml = ""
        self._exit_codes = exit_codes or {}

    def __call__(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if "/XML" in args:
            self.xml = Path(args[args.index("/XML") + 1]).read_text(encoding="utf-16")
        code = self._exit_codes.get(args[1], 0)
        return subprocess.CompletedProcess(args, code, "", "ERROR: Access is denied.")


def test_xml_is_a_one_shot_that_expires_and_escapes_paths() -> None:
    xml = task_xml(TASK, WAKE)
    assert "<StartBoundary>2026-10-20T07:00:00</StartBoundary>" in xml
    assert "<EndBoundary>2026-10-21T07:00:00</EndBoundary>" in xml
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    odd = WakeTask(TASK.name, Path(r"C:\a&b\pythonw.exe"), "<x>", TASK.working_dir, "PT5M")
    assert "a&amp;b" in task_xml(odd, WAKE) and "&lt;x&gt;" in task_xml(odd, WAKE)


def test_schedule_registers_from_a_temporary_utf16_file(tmp_path: Path) -> None:
    run = FakeSchtasks()
    WakeScheduler(TASK, tmp_path, run).schedule(WAKE)
    (call,) = run.calls
    assert call[:4] == [SCHTASKS, "/Create", "/TN", TASK.name] and call[-1] == "/F"
    assert "<Command>C:\\src\\Signal\\tools\\sleepmode\\.venv" in run.xml
    assert list(tmp_path.iterdir()) == []  # the XML file is cleaned up


def test_cancel_deletes_only_an_existing_task(tmp_path: Path) -> None:
    missing = FakeSchtasks({"/Query": 1})
    assert WakeScheduler(TASK, tmp_path, missing).cancel() is False
    assert [call[1] for call in missing.calls] == ["/Query"]
    present = FakeSchtasks()
    assert WakeScheduler(TASK, tmp_path, present).cancel() is True
    assert present.calls[1] == [SCHTASKS, "/Delete", "/TN", TASK.name, "/F"]
    with pytest.raises(ScheduleError):
        WakeScheduler(TASK, tmp_path, FakeSchtasks({"/Delete": 1})).cancel()
