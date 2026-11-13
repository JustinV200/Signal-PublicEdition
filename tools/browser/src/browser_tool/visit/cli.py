"""Entry point for `browser-tool-visit --config <toml> --plan <json> --out <json>`.

Checker v2 runs it once per site launch (refdocs/research/checker-v2.md section 3.1).
It loads one site config, refuses one that could be the desktop browser's (allow_all,
or the desktop .profile), checks the whole plan before Edge starts, runs the visit on
a local Edge (LocalBackend, never docker) that won't relaunch, and writes the out file
on every exit it controls. The launch borrows the desktop browser's saved sign-in
(cookie_store, BORROW: only cookies this config's policy allows, never saved back).
Logs go to stderr; page text goes only into the out file.
"""

import argparse
import asyncio
import json
import logging
import sys
import traceback
from pathlib import Path

from browser_tool.actions import ActionContext
from browser_tool.backends import LocalBackend
from browser_tool.config import ConfigError, Settings, load_settings, resolve_tool_path
from browser_tool.cookie_store import CookieMode
from browser_tool.credentials import LazyVaultFiller
from browser_tool.gates import DialogConfirmer
from browser_tool.visit.plan import PlanError, Target, parse_plan
from browser_tool.visit.result import STATUS_ERROR, STATUS_OK, VisitResult, write_out
from browser_tool.visit.runner import run_visit

logger = logging.getLogger("browser_tool")

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
# The MCP server's desktop profile, which a visit must never launch on.
DESKTOP_PROFILE_DIR = ".profile"
EXIT_OK = 0
EXIT_NOT_OK = 1


def main(argv: list[str] | None = None) -> None:
    """Run one visit and write its out file.

    Raises:
        SystemExit: 0 when the visit's status is ok, 1 otherwise (busy, error, a
            refused config or plan), or 1 if even the out file can't be written.
    """
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=LOG_FORMAT)
    result = _visit(args.config, args.plan)
    try:
        write_out(args.out, result)
    except OSError as error:
        logger.error("couldn't write the out file: %s", type(error).__name__)
        raise SystemExit(EXIT_NOT_OK) from None
    raise SystemExit(EXIT_OK if result.status == STATUS_OK else EXIT_NOT_OK)


def _visit(config_path: Path, plan_path: Path) -> VisitResult:
    """Load, check and run; any refusal or crash is an error result, logged."""
    try:
        settings = load_settings(config_path)
        _check_checker_config(settings)
        ctx = ActionContext.create(
            settings,
            DialogConfirmer(settings.gates.confirm_timeout_s),
            LazyVaultFiller(),
            LocalBackend(settings),
            allow_relaunch=False,
            holds_dialogs=False,
            cookie_mode=CookieMode.BORROW,
        )
        targets = _load_plan(plan_path, ctx)
    except (ConfigError, PlanError, ValueError, OSError) as error:
        logger.error("visit refused: %s", error)
        return VisitResult(STATUS_ERROR)
    try:
        return asyncio.run(run_visit(ctx, targets, settings.visit))
    except Exception as error:  # noqa: BLE001 - logged by type and frames only, never message
        frames = "".join(traceback.format_tb(error.__traceback__))
        logger.error("visit crashed: %s\n%s", type(error).__name__, frames)
        return VisitResult(STATUS_ERROR)


def _check_checker_config(settings: Settings) -> None:
    """Refuse a config that could be the desktop browser's: allow_all, or its profile.

    Raises:
        ConfigError: If [policy] allow_all is on or the profile is the desktop one.
    """
    if settings.policy.allow_all:
        raise ConfigError("a visit config must pin [policy] allow_all = false")
    profile = resolve_tool_path(settings.browser.profile_dir).resolve()
    if profile == resolve_tool_path(DESKTOP_PROFILE_DIR).resolve():
        raise ConfigError("a visit must not use the desktop browser's profile")


def _load_plan(plan_path: Path, ctx: ActionContext) -> tuple[Target, ...]:
    """The plan file's targets, checked against ctx's policy.

    Raises:
        OSError: If the file can't be read.
        PlanError: If it isn't JSON or fails parse_plan.
    """
    try:
        data = json.loads(plan_path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError):
        raise PlanError("the plan file isn't valid JSON") from None
    return parse_plan(data, ctx.policy)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="browser-tool-visit", description="Visit fixed pages and save their snapshots."
    )
    parser.add_argument("--config", type=Path, required=True, help="the site's checker config")
    parser.add_argument("--plan", type=Path, required=True, help="the plan JSON file")
    parser.add_argument("--out", type=Path, required=True, help="where to write the out JSON")
    return parser.parse_args(argv)
