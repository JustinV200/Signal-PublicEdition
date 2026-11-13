"""The reader's lockdown, output schema and argv: a claude with no tools at all.

The reader is the only model that sees page text, so it gets nothing to act with:
`--tools ""` (no built-in tools), `--strict-mcp-config` with no `--mcp-config` (no
MCP servers), `--restricted` in an empty folder, dontAsk, a $1.00 budget. Its init
event must list exactly StructuredOutput and no servers, or the launcher kills it
before the model's first turn (claude/init_check.py).
"""

import json
from pathlib import Path

from mail_digest.claude import Lockdown, array_of, build_command, closed_object
from mail_digest.settings import CHECK_BUDGET_USD, CHECK_MODEL, READER_PROMPT_PATH

READER_LOCKDOWN = Lockdown(
    tools=(),
    extra_allowed=(),
    disallowed=(),
    mcp_config=None,
    prompt_path=READER_PROMPT_PATH,
    expected_tools=frozenset({"StructuredOutput"}),
    expected_mcp_servers=(),
    model=CHECK_MODEL,
    max_budget_usd=CHECK_BUDGET_USD,
)
# What the reader may call an item.
ITEM_KINDS = ("assignment", "quiz", "event", "classwork")


def reader_schema() -> str:
    """The reader's --json-schema, as a compact string (findings/ validates every field)."""
    text = {"type": "string"}
    schema = closed_object(
        pages=array_of(key=text, readable={"type": "boolean"}, account=text),
        items=array_of(
            page=text,
            name=text,
            class_name=text,
            kind={"type": "string", "enum": list(ITEM_KINDS)},
            due=text,
            status_text=text,
            ref=text,
        ),
        suspicious={"type": "array", "items": text},
    )
    return json.dumps(schema, separators=(",", ":"))


def reader_command(claude_exe: Path) -> list[str]:
    """The reader's argv: no edit paths, so no --allowedTools, and an empty --tools."""
    return build_command(claude_exe, reader_schema(), (), READER_LOCKDOWN)
