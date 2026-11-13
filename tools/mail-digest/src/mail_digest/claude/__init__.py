"""mail_digest.claude: builds, runs and checks one locked-down claude process."""

from mail_digest.claude.command import build_command, edit_rules
from mail_digest.claude.context import build_context, target_lines
from mail_digest.claude.fields import clean_sentence, slugify
from mail_digest.claude.init_check import init_problems
from mail_digest.claude.launcher import (
    ClaudeNotFoundError,
    ClaudeRun,
    LaunchOptions,
    find_claude,
    read_events,
    run_claude,
)
from mail_digest.claude.lockdown import (
    DIGEST_LOCKDOWN,
    DISALLOWED_TOOLS,
    Lockdown,
)
from mail_digest.claude.prompt import compose_prompt
from mail_digest.claude.result import (
    RunResult,
    SuspiciousEmail,
    parse_result,
    run_cost,
    structured_output,
)
from mail_digest.claude.schema import array_of, closed_object, output_schema

__all__ = [
    "DIGEST_LOCKDOWN",
    "DISALLOWED_TOOLS",
    "ClaudeNotFoundError",
    "ClaudeRun",
    "LaunchOptions",
    "Lockdown",
    "RunResult",
    "SuspiciousEmail",
    "array_of",
    "build_command",
    "build_context",
    "clean_sentence",
    "closed_object",
    "compose_prompt",
    "edit_rules",
    "find_claude",
    "init_problems",
    "output_schema",
    "parse_result",
    "read_events",
    "run_claude",
    "run_cost",
    "slugify",
    "structured_output",
    "target_lines",
]
