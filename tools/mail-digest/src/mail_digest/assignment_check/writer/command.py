"""The writer's lockdown, output schema and argv: v1's locked-down claude without mail.

Its cwd is life/, with --restricted, `--tools Read,Edit`, Read plus the exact
Edit(/<path>) rules of this run, v1's DISALLOWED_TOOLS, and --strict-mcp-config with
no MCP servers at all. Its init event must list exactly Read, Edit and
StructuredOutput and no servers. It only ever sees validated fields (findings/),
never page text, and its edits go through the v1 guard with the (site) tag and the
no-untick rule (steps.run_guarded_edit, kb.LineRules).
"""

import json
from pathlib import Path

from mail_digest.claude import DISALLOWED_TOOLS, Lockdown, build_command, closed_object
from mail_digest.kb import LineRules
from mail_digest.settings import CHECK_BUDGET_USD, CHECK_MODEL, SITE_TAG, WRITER_PROMPT_PATH

WRITER_TOOLS = ("Read", "Edit")
WRITER_LOCKDOWN = Lockdown(
    tools=WRITER_TOOLS,
    extra_allowed=(),
    disallowed=DISALLOWED_TOOLS,
    mcp_config=None,
    prompt_path=WRITER_PROMPT_PATH,
    expected_tools=frozenset({*WRITER_TOOLS, "StructuredOutput"}),
    expected_mcp_servers=(),
    model=CHECK_MODEL,
    max_budget_usd=CHECK_BUDGET_USD,
)
# The guard's rules for a site run: lines end in (site), and nothing is unticked.
SITE_RULES = LineRules(tag=SITE_TAG, forbid_untick=True)


def writer_schema() -> str:
    """The writer's --json-schema: only a summary, which the runner logs with %r."""
    return json.dumps(closed_object(summary={"type": "string"}), separators=(",", ":"))


def writer_command(claude_exe: Path, editable: tuple[str, ...]) -> list[str]:
    """The writer's argv, with one exact Edit rule per editable file."""
    return build_command(claude_exe, writer_schema(), editable, WRITER_LOCKDOWN)
