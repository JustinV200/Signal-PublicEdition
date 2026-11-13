"""The check's own record for the owner: last-check.json, and the lines the CLI prints.

Links can't go into life/ (the guard's line rules forbid URLs), so they live here:
every validated item with the link the runner built, and every page problem. The
file is overwritten each check. Nothing in it is shown to a model.
"""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from mail_digest.assignment_check.findings import Findings

log = logging.getLogger(__name__)


def write_last_check(path: Path, findings: Findings, now: datetime) -> None:
    """Write this check's items and problems to path. Never raises: a failure is logged."""
    data = {
        "checked_at": now.isoformat(timespec="seconds"),
        "items": [asdict(item) for item in findings.items],
        "problems": [asdict(problem) for problem in findings.problems],
    }
    temp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temp, path)
    except OSError as error:
        log.warning("couldn't write %s: %s", path, error)


def item_lines(findings: Findings) -> list[str]:
    """One line per item for the foreground output, with its status, due date and link."""
    lines = []
    for item in findings.items:
        flag = " OVERDUE" if item.overdue else " DUE SOON" if item.due_soon else ""
        due = f" (due {item.due})" if item.due else ""
        lines.append(f"[{item.course}] {item.name}{due}: {item.status}{flag}\n    {item.link}")
    for problem in findings.problems:
        lines.append(f"[{problem.course}] not read: {problem.page} ({problem.reason})")
    return lines or ["No items found."]
