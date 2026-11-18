"""`console doctor` exits 1 only when a row is a fail; attention rows print their fix and exit 0.

With --summary-json the first fail row also ends the output as setup's JSON summary line.
"""

import argparse
import json

import pytest

from signal_console.cli import doctor_command
from signal_console.health import ATTENTION, FAIL, OK, HealthRow

ATTENTION_ROW = HealthRow("server", "Console server", ATTENTION, "not running", "Off.", "Start it.")
FAIL_ROW = HealthRow("edge", "Microsoft Edge", FAIL, "missing", "No Edge.", "Install it.")
LATER_FAIL_ROW = HealthRow("turn-hook", "Turn hook", FAIL, "missing", "Not added.", "Add it.")
OK_ROW = HealthRow("web-build", "Console page", OK, "built", "Built.")
FAIL_SUMMARY = {"words": "Microsoft Edge: No Edge.", "fix": "Install it.", "command": None}


@pytest.mark.parametrize(
    ("rows", "exit_code", "summaries"),
    [
        ([OK_ROW, ATTENTION_ROW], 0, []),
        ([OK_ROW, ATTENTION_ROW, FAIL_ROW, LATER_FAIL_ROW], 1, [FAIL_SUMMARY]),
    ],
)
def test_doctor_exits_1_only_on_a_fail_row(monkeypatch, capsys, rows, exit_code, summaries):
    # Fixed rows: the real checks would read this checkout's .state and settings.
    monkeypatch.setattr(doctor_command, "health_rows", lambda paths: rows)

    assert doctor_command.run_doctor(argparse.Namespace(summary_json=True)) == exit_code
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith("attention") and "Fix: Start it." in lines[1]
    # Attention rows alone add no summary; a fail adds exactly one, for the first fail row.
    assert [json.loads(line) for line in lines[len(rows) :]] == summaries
