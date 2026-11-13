"""The lockdown one `claude -p` run gets: its tools, rules, MCP config and expected init.

command.build_command turns a Lockdown into flags, and init_check.init_problems checks
claude's init event against the same value, so the two can't drift apart. The digest's
is DIGEST_LOCKDOWN (today's flags); checker v2's reader and writer bring their own.
"""

from dataclasses import dataclass
from pathlib import Path

from mail_digest.settings import DIGEST_PROMPT_PATH, MAX_BUDGET_USD, MCP_CONFIG_PATH, MODEL

# Every run is dontAsk: anything not in the allow list is denied, and nobody is asked.
EXPECTED_PERMISSION_MODE = "dontAsk"

DIGEST_BUILTIN_TOOLS = ("Read", "Edit")
# The runner lists the accounts and runs the searches itself (mailbox/) and puts the
# messages in the run context, so the model only reads messages and threads.
MAIL_READ_TOOLS = ("mcp__mail__mail_read", "mcp__mail__mail_thread")
MAIL_RUNNER_TOOLS = ("mcp__mail__mail_accounts", "mcp__mail__mail_search")

DISALLOWED_TOOLS = (
    "Bash",
    "PowerShell",
    "WebFetch",
    "WebSearch",
    "Write",
    "NotebookEdit",
    "Agent",
    "mcp__mail__mail_draft",
    "mcp__mail__mail_send_draft",
)


@dataclass(frozen=True)
class Lockdown:
    """Everything that decides what one claude run can do, and what its init must show.

    tools: the built-in tools (--tools). Every one but Edit is also allowed outright;
      Edit is allowed only on the run's exact files. Empty means no built-in tools.
    extra_allowed: allow rules after the Edit rules (the digest's mail read tools).
    disallowed: --disallowedTools (left out when empty).
    mcp_config: the --mcp-config file, or None for no MCP servers at all.
    prompt_path: the system prompt file, passed as --append-system-prompt-file. For a
      run that edits life/ it's composed just before launch (prompt.py).
    expected_tools: exactly the tools the init event must list.
    expected_mcp_servers: exactly the {name, status} entries it must list.
    model, max_budget_usd: --model and --max-budget-usd.
    """

    tools: tuple[str, ...]
    extra_allowed: tuple[str, ...]
    disallowed: tuple[str, ...]
    mcp_config: Path | None
    prompt_path: Path
    expected_tools: frozenset[str]
    expected_mcp_servers: tuple[dict, ...]
    model: str
    max_budget_usd: str


# StructuredOutput is how --json-schema returns the result.
DIGEST_LOCKDOWN = Lockdown(
    tools=DIGEST_BUILTIN_TOOLS,
    extra_allowed=MAIL_READ_TOOLS,
    disallowed=(*DISALLOWED_TOOLS, *MAIL_RUNNER_TOOLS),
    mcp_config=MCP_CONFIG_PATH,
    prompt_path=DIGEST_PROMPT_PATH,
    expected_tools=frozenset({*DIGEST_BUILTIN_TOOLS, "StructuredOutput", *MAIL_READ_TOOLS}),
    expected_mcp_servers=({"name": "mail", "status": "connected"},),
    model=MODEL,
    max_budget_usd=MAX_BUDGET_USD,
)
