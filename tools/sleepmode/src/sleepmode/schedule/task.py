"""WakeScheduler: a one-shot per-user scheduled task that runs `sleepmode wake` at the wake time.

The task is registered from XML with `schtasks /Create /XML`: the XML's local
StartBoundary works in any Windows locale (schtasks' /SD date format doesn't). It runs
as the current user, only while they're logged on, without elevation, so no admin
rights are needed. It deletes itself a day after its time (EndBoundary +
DeleteExpiredTaskAfter) in case `wake` couldn't remove it.
"""

import logging
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

log = logging.getLogger(__name__)

# The full path, so a schtasks.exe in the working folder or on PATH can't stand in for it.
SCHTASKS = str(Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "schtasks.exe")
# Console programs started from the windowless keeper or wake task would otherwise flash a window.
CREATE_NO_WINDOW = 0x08000000
# How long the expired task lingers before Task Scheduler deletes it.
TASK_EXPIRY = timedelta(days=1)
# schtasks normally answers in well under a second; a hung one mustn't hang a wake.
SCHTASKS_TIMEOUT_S = 15.0
_XML_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

RunCommand = Callable[[list[str]], subprocess.CompletedProcess[str]]


class ScheduleError(RuntimeError):
    """schtasks refused to create or delete the wake task."""


# Everything WakeScheduler can raise: a refusal, a file or process error, or a schtasks
# that hung past SCHTASKS_TIMEOUT_S (subprocess.TimeoutExpired).
SCHEDULER_FAILURES = (ScheduleError, OSError, subprocess.SubprocessError)


@dataclass(frozen=True)
class WakeTask:
    """What the wake task runs.

    Attributes:
        name: The task's name in the Task Scheduler root folder.
        command: The program, e.g. the venv's pythonw.exe.
        arguments: Its command line, e.g. "-m sleepmode wake --reason schedule".
        working_dir: Its working folder.
        time_limit: ISO 8601 duration after which Task Scheduler stops a hung run.
    """

    name: str
    command: Path
    arguments: str
    working_dir: Path
    time_limit: str


def task_xml(task: WakeTask, when: datetime) -> str:
    """Build the Task Scheduler XML for a one-shot run at `when` (naive local time)."""
    start = when.strftime(_XML_TIME_FORMAT)
    end = (when + TASK_EXPIRY).strftime(_XML_TIME_FORMAT)
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Signal sleep mode: wake the screens (tools/sleepmode).</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <StartBoundary>{start}</StartBoundary>
      <EndBoundary>{end}</EndBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <DeleteExpiredTaskAfter>PT0S</DeleteExpiredTaskAfter>
    <ExecutionTimeLimit>{escape(task.time_limit)}</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(task.command))}</Command>
      <Arguments>{escape(task.arguments)}</Arguments>
      <WorkingDirectory>{escape(str(task.working_dir))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def create_args(name: str, xml_path: Path) -> list[str]:
    """schtasks arguments that create (or with /F replace) the task from an XML file."""
    return [SCHTASKS, "/Create", "/TN", name, "/XML", str(xml_path), "/F"]


def query_args(name: str) -> list[str]:
    """schtasks arguments that succeed only if the task exists."""
    return [SCHTASKS, "/Query", "/TN", name]


def delete_args(name: str) -> list[str]:
    """schtasks arguments that delete the task without asking."""
    return [SCHTASKS, "/Delete", "/TN", name, "/F"]


def run_hidden(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a console command with no window, capturing its output.

    Raises:
        subprocess.TimeoutExpired: It ran past SCHTASKS_TIMEOUT_S (it's killed first).
        OSError: It couldn't be started.
    """
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        # Output in an unexpected code page must not turn a refusal into a crash.
        errors="replace",
        check=False,
        creationflags=CREATE_NO_WINDOW,
        timeout=SCHTASKS_TIMEOUT_S,
    )


class WakeScheduler:
    """Creates, replaces and removes the one wake task."""

    def __init__(self, task: WakeTask, xml_dir: Path, run: RunCommand = run_hidden) -> None:
        """Configure the scheduler. Nothing runs until schedule() or cancel().

        Args:
            task: The task's name and command.
            xml_dir: Where to write the XML briefly while registering (the state folder).
            run: Runs schtasks; tests pass a fake.
        """
        self._task = task
        self._xml_dir = xml_dir
        self._run = run

    def schedule(self, when: datetime) -> None:
        """Create the wake task for `when`, replacing any earlier one.

        Raises:
            ScheduleError: schtasks refused.
            OSError: The XML file couldn't be written.
            subprocess.TimeoutExpired: schtasks hung (from run_hidden).
        """
        self._xml_dir.mkdir(parents=True, exist_ok=True)
        xml_path = self._xml_dir / "wake-task.xml"
        # schtasks expects UTF-16 XML (the declaration says so).
        xml_path.write_text(task_xml(self._task, when), encoding="utf-16")
        try:
            self._check(self._run(create_args(self._task.name, xml_path)), "create")
        finally:
            xml_path.unlink(missing_ok=True)
        log.info("wake task %r set for %s", self._task.name, when.isoformat(timespec="minutes"))

    def cancel(self) -> bool:
        """Delete the wake task if there is one.

        Returns:
            True if a task was deleted, False if there was none.

        Raises:
            ScheduleError: The task exists but schtasks couldn't delete it.
            subprocess.TimeoutExpired: schtasks hung (from run_hidden).
        """
        if self._run(query_args(self._task.name)).returncode != 0:
            return False
        self._check(self._run(delete_args(self._task.name)), "delete")
        log.info("wake task %r removed", self._task.name)
        return True

    def _check(self, completed: subprocess.CompletedProcess[str], action: str) -> None:
        if completed.returncode != 0:
            output = (completed.stderr or completed.stdout or "").strip()
            raise ScheduleError(f"couldn't {action} the wake task: {output}")
