"""`whiteboard todo`: --if-running never starts a daemon (the 06:00 task)."""

import argparse

from whiteboard.cli.commands.views import todo as todo_command
from whiteboard.config import Settings
from whiteboard.daemon_client import DaemonStartError


class NoDaemon:
    """A connection that finds no daemon and may not start one."""

    def __init__(self, is_auto_start: bool) -> None:
        self.is_auto_start = is_auto_start

    def call(self, operation):
        raise DaemonStartError("The whiteboard daemon isn't running.")


def run(monkeypatch, action: str, item: str | None, if_running: bool) -> tuple[int, list[bool]]:
    started: list[bool] = []

    def connect(args, settings, is_auto_start=True):
        started.append(is_auto_start)
        return NoDaemon(is_auto_start)

    monkeypatch.setattr(todo_command, "daemon_connection", connect)
    args = argparse.Namespace(action=action, item=item, if_running=if_running, config=None)
    return todo_command.run_todo(args, Settings()), started


def test_the_daily_sync_does_nothing_without_a_daemon(monkeypatch, capsys) -> None:
    code, started = run(monkeypatch, "sync", None, if_running=True)
    assert code == 0 and started == [False]
    assert "isn't running" in capsys.readouterr().out
