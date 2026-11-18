"""`console doctor`: print the console's health rows, one line each, and exit 1 on a fail row.

Every check is a local read (signal_console.health), so it works with the server
down and changes nothing. Attention rows print as not ok with their fix, but only
a fail row (the console can't work) makes the exit code 1. With `--summary-json`
the setup tool's verify check also gets the first fail row as one JSON line
(the contract is in tools/setup/README.md, "Verify checks").
"""

import argparse
import json

from signal_console.health import FAIL, OK, HealthPaths, HealthRow, health_rows

# Each level as a word, so the state never rests on colour.
LEVEL_WORDS = {OK: "ok", FAIL: "FAIL"}
ATTENTION_WORD = "attention"
LEVEL_WIDTH = len(ATTENTION_WORD)


def run_doctor(args: argparse.Namespace) -> int:
    """Print every health row, then with --summary-json the first fail row as JSON.

    Returns 1 if any row is a fail, else 0.
    """
    rows = health_rows(HealthPaths())
    for row in rows:
        print(doctor_line(row))
    failed = [row for row in rows if row.level == FAIL]
    if args.summary_json and failed:
        print(json.dumps(summary(failed[0])))
    return 1 if failed else 0


def summary(row: HealthRow) -> dict[str, str | None]:
    """A row as the setup tool's summary line: {words, fix, command}."""
    return {"words": f"{row.name}: {row.words}", "fix": row.fix, "command": row.command}


def doctor_line(row: HealthRow) -> str:
    """One row as a line: level word, name, what was found, then the fix and command if any."""
    level = LEVEL_WORDS.get(row.level, ATTENTION_WORD)
    line = f"{level:<{LEVEL_WIDTH}}  {row.name}: {row.words}"
    if row.fix:
        line += f" Fix: {row.fix}"
    if row.command:
        line += f" Run: {row.command}"
    return line
