"""The result record every phase 0 probe returns, and the report printer."""

from collections.abc import Awaitable
from dataclasses import dataclass


@dataclass(frozen=True)
class Result:
    """One check: its id from the design doc's phase 0 list, pass or fail, and evidence."""

    check: str
    passed: bool
    detail: str


async def guarded(check: str, awaitable: Awaitable[Result]) -> Result:
    """Await one check; if it raises, report it as failed with the error as evidence."""
    try:
        return await awaitable
    except Exception as error:  # noqa: BLE001 - a crashed check is reported, not hidden
        first_line = str(error).splitlines()[0] if str(error) else ""
        return Result(check, False, f"crashed: {type(error).__name__}: {first_line}")


def print_report(results: list[Result]) -> None:
    """Print one line per check, then the pass count."""
    for result in results:
        print(f"[{'PASS' if result.passed else 'FAIL'}] {result.check}: {result.detail}")
    passed = sum(result.passed for result in results)
    print(f"\n{passed}/{len(results)} checks passed")
