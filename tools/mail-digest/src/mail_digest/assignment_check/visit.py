"""One site's visit: write its plan, run `browser-tool-visit` with the kill, read its out file.

The browser tool does the visiting (tools/browser/src/browser_tool/visit/): fixed URLs,
snapshots, and on Moodle the one vault fill on CAS. No model is involved. This module
only drives it: the plan goes in a file, the launch runs hidden through run_hidden
and is killed (its whole tree, Edge included) after VISIT_TIMEOUT_S, and the out file
is read and checked. The out file from an earlier run is deleted first, so a killed
launch can't leave stale pages behind; a missing or malformed file is an error.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mail_digest.assignment_check.courses import Page, plan_json
from mail_digest.child_env import run_hidden
from mail_digest.settings import BROWSER_PROJECT, CHECK_DIR, VISIT_TIMEOUT_S

log = logging.getLogger(__name__)

# The launch's status, as browser_tool.visit.result writes it.
LAUNCH_OK = "ok"
LAUNCH_BUSY = "busy"
LAUNCH_ERROR = "error"
LAUNCH_STATUSES = (LAUNCH_OK, LAUNCH_BUSY, LAUNCH_ERROR)
# A page's status.
PAGE_OK = "ok"
PAGE_STATUSES = (PAGE_OK, "error", "login_needed", "google_signin_needed")


@dataclass(frozen=True)
class VisitedPage:
    """One page's outcome: its plan key, status, and text (only when status is ok)."""

    key: str
    status: str
    text: str = ""


@dataclass(frozen=True)
class SiteVisit:
    """One launch's outcome: its status and the pages it got to."""

    status: str
    pages: tuple[VisitedPage, ...] = ()


def config_path(site: str) -> Path:
    """The site's committed checker config in tools/browser."""
    return BROWSER_PROJECT / f"browser-checker-{site}.toml"


def launch_paths(site: str, work_dir: Path = CHECK_DIR) -> tuple[Path, Path]:
    """(the plan file, the out file) of site's launch, in the checker's .state folder."""
    return work_dir / f"plan-{site}.json", work_dir / f"pages-{site}.json"


def visit_command(site: str, plan_path: Path, out_path: Path) -> list[str]:
    """The argv of one launch. A list, so no shell parses it."""
    return [
        "uv", "run", "--project", str(BROWSER_PROJECT), "--frozen", "--no-sync",
        "browser-tool-visit",
        "--config", str(config_path(site)),
        "--plan", str(plan_path),
        "--out", str(out_path),
    ]  # fmt: skip


def run_launch(argv: list[str]) -> None:
    """Run one launch hidden, killing its whole tree (Edge too) after VISIT_TIMEOUT_S.

    Its exit code doesn't matter: the out file says what happened. Never raises.
    """
    run_hidden("browser-tool-visit", argv, VISIT_TIMEOUT_S)


def visit_site(
    site: str,
    pages: tuple[Page, ...],
    launch: Callable[[list[str]], None] = run_launch,
    work_dir: Path = CHECK_DIR,
) -> SiteVisit:
    """Run one launch for site's pages and return what it found.

    launch(argv) runs the command (tests pass a fake). Never raises: a plan or out
    file that can't be written or read is a LAUNCH_ERROR (logged).
    """
    plan_path, out_path = launch_paths(site, work_dir)
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        out_path.unlink(missing_ok=True)
        plan_path.write_text(plan_json(pages), encoding="utf-8")
    except OSError as error:
        log.error("couldn't set up the %s visit: %s", site, error)
        return SiteVisit(LAUNCH_ERROR)
    launch(visit_command(site, plan_path, out_path))
    return read_out(out_path, {page.key for page in pages})


def read_out(out_path: Path, keys: set[str]) -> SiteVisit:
    """The out file as a SiteVisit, or LAUNCH_ERROR if it's missing or malformed.

    keys are the plan's keys; a page with another key, or any bad field, makes the
    whole file malformed, since the browser tool never writes one like that.
    """
    try:
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as error:
        log.error("no usable visit out file %s: %s", out_path.name, type(error).__name__)
        return SiteVisit(LAUNCH_ERROR)
    status = data.get("status") if isinstance(data, dict) else None
    entries = data.get("pages") if isinstance(data, dict) else None
    if status not in LAUNCH_STATUSES or not isinstance(entries, list):
        log.error("malformed visit out file %s", out_path.name)
        return SiteVisit(LAUNCH_ERROR)
    pages = [_page(entry, keys) for entry in entries]
    if None in pages:
        log.error("malformed page in visit out file %s", out_path.name)
        return SiteVisit(LAUNCH_ERROR)
    return SiteVisit(status, tuple(pages))


def _page(entry: object, keys: set[str]) -> VisitedPage | None:
    """One out-file page, or None if it's malformed."""
    if not isinstance(entry, dict):
        return None
    key, status, text = entry.get("key"), entry.get("status"), entry.get("text", "")
    if key not in keys or status not in PAGE_STATUSES or not isinstance(text, str):
        return None
    return VisitedPage(key, status, text if status == PAGE_OK else "")
