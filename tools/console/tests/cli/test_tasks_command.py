"""`console tasks set` saves the task, and claims the console only when no open session holds it."""

import pytest
from signal_orchestrator import SOCKET_ENV, TOKEN_ENV
from signal_orchestrator.testing import fake_inbox, unused_pipe_address
from signal_tasks import read_tasks

from signal_console.cli import main, tasks_command
from signal_console.orchestrator import Claim, liveness, read_claim, write_claim


def _refuse_listing(path: str) -> list[str]:
    raise FileNotFoundError(path)


@pytest.mark.parametrize(
    "case", ["missing", "dead", "alive", "no inbox variables", "pipes unlisted"]
)
async def test_tasks_set_claims_only_a_missing_or_closed_claim(tmp_path, monkeypatch, case):
    # Temp state and .env only; the caller's inbox is a fake one, never this session's own.
    monkeypatch.setattr(tasks_command, "STATE_DIR", tmp_path)
    monkeypatch.setattr(tasks_command, "ENV_FILE_PATH", tmp_path / ".env")
    caller = unused_pipe_address()
    if case == "no inbox variables":
        monkeypatch.delenv(SOCKET_ENV, raising=False)
        monkeypatch.delenv(TOKEN_ENV, raising=False)
    else:
        monkeypatch.setenv(SOCKET_ENV, caller)
        monkeypatch.setenv(TOKEN_ENV, "caller-token")

    # A real pipe served by a fake inbox stands for an open session.
    async with fake_inbox() as open_session:
        dead = unused_pipe_address()
        held = {"dead": dead, "alive": open_session.address, "pipes unlisted": dead}.get(case)
        if held is not None:
            write_claim(tmp_path, Claim(held, "old-token", "old", "2026-10-22T10:00:00+00:00"))
        if case == "pipes unlisted":
            # Liveness can't be told, so the held claim may be live: it must stay.
            monkeypatch.setattr(liveness, "listdir", _refuse_listing)

        exit_code = main(["tasks", "set", "t1", "--name", "A task"])

    assert exit_code == 0
    assert [task.id for task in read_tasks(tmp_path / "tasks.json").tasks] == ["t1"]
    claim = read_claim(tmp_path)
    if case in ("missing", "dead"):
        assert claim is not None and claim.socket == caller and claim.token == "caller-token"
        assert claim.label  # the local time, so it reads apart from earlier sessions
    elif case in ("alive", "pipes unlisted"):
        assert claim is not None and claim.socket == held  # never replaced
    else:
        assert claim is None
