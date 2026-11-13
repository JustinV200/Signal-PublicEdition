"""The checker's real world: default_deps for a real check, and what --dry-run prints.

default_deps wires run.CheckDeps to the browser tool's visit command, the two locked
claudes (the reader in its empty folder, the writer in life/), audiohub with source
assignment-check, the self-only digest email and the whiteboard. A dry run starts
nothing: it prints both plans and every argv a check would run.
"""

import functools
from datetime import datetime
from pathlib import Path

from mail_digest.announce import send_notify
from mail_digest.assignment_check.check_config import load_check_config
from mail_digest.assignment_check.courses import VISIT_ORDER, plan_json, site_pages
from mail_digest.assignment_check.reader import READER_LOCKDOWN, reader_command
from mail_digest.assignment_check.run import MISSING_CLAUDE, CheckDeps
from mail_digest.assignment_check.visit import launch_paths, visit_command, visit_site
from mail_digest.assignment_check.writer import WRITER_LOCKDOWN, writer_command
from mail_digest.claude import (
    ClaudeNotFoundError,
    ClaudeRun,
    LaunchOptions,
    compose_prompt,
    find_claude,
    run_claude,
)
from mail_digest.digest_email import send_digest_email
from mail_digest.kb import find_targets
from mail_digest.settings import (
    CHECK_CONFIG_PATH,
    CHECK_NOTIFY_SOURCE,
    LAST_CHECK_PATH,
    LIFE_DIR,
    READER_DIR,
    READER_STDERR_PATH,
    READER_TIMEOUT_S,
    REJECTED_DIR,
    SITE_TAG,
    STATE_PATH,
    WRITER_PROMPT_PATH,
    WRITER_ROUTINE_PATH,
    WRITER_STDERR_PATH,
    WRITER_TIMEOUT_S,
)
from mail_digest.steps import refresh_todo_board

READER_OPTIONS = LaunchOptions(
    cwd=READER_DIR,
    timeout_s=READER_TIMEOUT_S,
    stderr_path=READER_STDERR_PATH,
    lockdown=READER_LOCKDOWN,
)
WRITER_OPTIONS = LaunchOptions(
    cwd=LIFE_DIR,
    timeout_s=WRITER_TIMEOUT_S,
    stderr_path=WRITER_STDERR_PATH,
    lockdown=WRITER_LOCKDOWN,
)


def default_deps() -> CheckDeps:
    """The real world (see the module docstring).

    Raises:
        CheckConfigError: If assignment-check.toml is missing or has a bad value.
    """
    return CheckDeps(
        life_dir=LIFE_DIR,
        state_path=STATE_PATH,
        rejected_dir=REJECTED_DIR,
        last_check_path=LAST_CHECK_PATH,
        config=load_check_config(CHECK_CONFIG_PATH),
        visit=visit_site,
        read=_read,
        write=_write,
        notify=functools.partial(send_notify, source=CHECK_NOTIFY_SOURCE),
        send_email=send_digest_email,
        refresh_board=refresh_todo_board,
        now=lambda: datetime.now().astimezone(),
        find_claude=find_claude,
    )


def dry_run_lines() -> list[str]:
    """Both visit plans and argvs, and the reader's and writer's argvs. Starts nothing.

    Raises:
        CheckConfigError: If assignment-check.toml is missing or has a bad value.
    """
    config = load_check_config(CHECK_CONFIG_PATH)
    claude = _claude_or_placeholder()
    lines = []
    for site in VISIT_ORDER:
        plan_path, out_path = launch_paths(site)
        lines += [f"{site} plan:", plan_json(site_pages(site, config))]
        lines.append(f"{site} visit: {visit_command(site, plan_path, out_path)}")
    lines.append(f"reader (one per site): {reader_command(claude)}")
    targets = find_targets(LIFE_DIR, datetime.now().date())
    lines.append(f"writer: {writer_command(claude, targets.editable)}")
    return lines


def _read(argv: list[str], context: str) -> ClaudeRun:
    """Run the reader in its own empty folder (made on first use)."""
    READER_DIR.mkdir(parents=True, exist_ok=True)
    return run_claude(argv, context, READER_OPTIONS)


def _write(argv: list[str], context: str) -> ClaudeRun:
    """Compose the writer's system prompt file (routine + shared rules, tag (site)), then run it.

    Raises OSError if the prompt can't be written or claude can't start; the guarded
    edit counts that as a failed writer.
    """
    compose_prompt(WRITER_ROUTINE_PATH, SITE_TAG, WRITER_PROMPT_PATH)
    return run_claude(argv, context, WRITER_OPTIONS)


def _claude_or_placeholder() -> Path:
    """claude.exe for the dry run's argvs, or a placeholder if it isn't found."""
    try:
        return find_claude()
    except ClaudeNotFoundError:
        return MISSING_CLAUDE
