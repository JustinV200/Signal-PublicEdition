"""The consent page's plain words: one line per finished tool, saying what Claude may do
without asking once the tool is added to Claude Code.

build_plan makes one line per tool from what that tool actually grants; summary_lines
shows them before the exact entries (the setup window folds those under Show exact
entries). A tool's words are its registry `consent`, used only once something granting
is in place: allow rules or hooks in the plan, or a done step that registers an
unattended Claude run. So a browser whose auto-approve step was skipped never claims it.
Known gap: one `consent` covers a tool's own rules and its steps' rules alike, so a future
tool with both would over-claim until its optional step is done (none has both today).
"""

from typing import NamedTuple

from signal_setup.registry import Tool

# A tool that grants something but has no registry `consent`: true, if vague.
UNWORDED = "adds entries Claude Code uses without asking each time; see the exact entries."
# A tool whose MCP server is added with none of its actions auto-approved.
ASKS_EACH_TIME = "Claude can use its tools, but asks you each time."
ADDS_NOTHING = "adds nothing to Claude Code."
# Added to the line of the tool whose finished step sets the status line (usage); the
# writer keeps a status line the user already has.
STATUSLINE = (
    "It also sets Claude Code's status line in your user settings, unless you have your own."
)


class Grants(NamedTuple):
    """What one finished tool grants, as the plan worked it out."""

    allow: list[str]  # its allow rules, already filtered to wired servers
    has_servers: bool  # it adds at least one MCP server
    sets_statusline: bool  # a done step of it sets the user's status line
    runs_claude: bool  # a done step of it registers an unattended Claude run


def consent_line(tool: Tool, grants: Grants) -> str:
    """`<tool name>: <what Claude may do without asking>`, from what `tool` grants."""
    if grants.allow or tool.hooks or grants.runs_claude:
        words = tool.consent or UNWORDED
    elif grants.has_servers:
        words = ASKS_EACH_TIME
    else:
        words = ADDS_NOTHING
    if grants.sets_statusline:
        words = f"{words} {STATUSLINE}"
    return f"{tool.name}: {words}"
