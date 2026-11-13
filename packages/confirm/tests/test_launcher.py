"""The parent side fails closed: only a clean "allow" from the child approves.

Fake children are tiny `python -c` scripts, so no window appears.
"""

import sys
import time

import pytest

from signal_confirm import confirm
from signal_confirm.launcher import CHILD_COMMAND, run_child, run_child_async

DEADLINE_S = 30.0
TINY_DEADLINE_S = 0.5
# Well under the hung child's 30 s sleep: proves it was killed, not waited for.
KILL_BUDGET_S = 10.0
HUNG_CHILD = (sys.executable, "-c", "import time; time.sleep(30)")


def python_child(code: str) -> tuple[str, ...]:
    return (sys.executable, "-c", code)


def test_a_clean_allow_from_the_child_approves():
    assert run_child(python_child("print('allow')"), b"", DEADLINE_S) is True


@pytest.mark.parametrize(
    "command",
    [
        python_child("print('deny')"),
        python_child("import sys; print('allow'); sys.exit(1)"),
        python_child("print('allow please')"),
        ("C:/no/such/python.exe",),
    ],
    ids=["deny", "crash-after-allow", "garbled", "cannot-start"],
)
def test_anything_but_a_clean_allow_denies(command):
    assert run_child(command, b"", DEADLINE_S) is False


def test_the_real_child_denies_a_malformed_request_without_a_window():
    assert run_child(CHILD_COMMAND, b"not json", DEADLINE_S) is False


def test_invalid_arguments_deny_without_starting_a_child():
    assert confirm("title", "message", timeout_s=float("nan")) is False


def test_a_hung_child_is_killed_at_the_deadline_and_denies():
    started = time.monotonic()
    assert run_child(HUNG_CHILD, b"", TINY_DEADLINE_S) is False
    assert time.monotonic() - started < KILL_BUDGET_S


@pytest.mark.asyncio
async def test_async_fails_closed_on_a_hang_and_approves_only_a_clean_allow():
    started = time.monotonic()
    assert await run_child_async(HUNG_CHILD, b"", TINY_DEADLINE_S) is False
    assert time.monotonic() - started < KILL_BUDGET_S
    assert await run_child_async(("C:/no/such/python.exe",), b"", DEADLINE_S) is False
    assert await run_child_async(python_child("print('allow')"), b"", DEADLINE_S) is True
