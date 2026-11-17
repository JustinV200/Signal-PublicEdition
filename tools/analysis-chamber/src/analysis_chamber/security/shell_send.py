"""PreToolUse hook that stops shell commands and scripts from sending anything.

MCP send tools are blocked by send_block_hook; this covers the routes around them
(spike review, finding A): gmcli, the Signal tool CLIs and projects, the credential and
state files behind them, and send APIs called directly. It checks Bash and PowerShell
commands and script files being written; Python files get the narrower
PYTHON_SEND_RULES, where a bare CLI name on a line is code, not a command. Allowed on
purpose: `analysis-chamber gpu` and `install`, and paths inside the chamber's own tool
folder (its venv's analysis-chamber.exe, the playbook). The chamber's .state files
still hit the credential rule.

Also denied: any absolute path under <repo_root>/tools or <repo_root>/packages outside
tools/analysis-chamber, so a tool can't be run by its full path.

TODO: obfuscated code (base64, string concatenation, env-var indirection) and generic
HTTP POSTs to hosts not in SHELL_SEND_RULES still get through. Risk recorded in the
package README.
"""

from typing import TYPE_CHECKING, Any

from analysis_chamber.guard import is_under
from analysis_chamber.security.common import (
    allow,
    code_text,
    collapse_escapes,
    deny,
    is_python_file,
    path_candidates,
    resolve_against,
)
from analysis_chamber.security.rules.shell_send_rules import PYTHON_SEND_RULES, SHELL_SEND_RULES

if TYPE_CHECKING:  # type only: agents imports this package, so no runtime import back
    from analysis_chamber.agents.context import RunContext

_CHAMBER_DIR_NAME = "analysis-chamber"


def _names_tool_path(text: str, ctx: "RunContext") -> bool:
    """Whether text names a path under the repo's tools/ or packages/, outside the chamber."""
    repo_root = ctx.config.repo_root
    chamber_dir = repo_root / "tools" / _CHAMBER_DIR_NAME
    for raw in path_candidates(text):
        path = resolve_against(raw.rstrip("\\/"), ctx.run_dir)
        in_tools = is_under(path, repo_root / "tools") or is_under(path, repo_root / "packages")
        if in_tools and not is_under(path, chamber_dir):
            return True
    return False


def shell_send_reason(code: str, ctx: "RunContext", *, is_python: bool = False) -> str | None:
    """Why a command or script could send, or None when it looks safe.

    Args:
        code: A shell command or script text.
        ctx: The run (repo_root, run_dir).
        is_python: The text is a .py or .ipynb file, not shell.

    Returns:
        The deny reason, or None.
    """
    text = collapse_escapes(code)
    for label, pattern in PYTHON_SEND_RULES if is_python else SHELL_SEND_RULES:
        if pattern.search(text):
            return f"Blocked: this uses {label}, which can send or holds the user's credentials."
    if _names_tool_path(text, ctx):
        return "Blocked: this runs or reads a Signal tool or package, which can send."
    return None


async def shell_send_hook(
    hook_input: dict[str, Any], tool_use_id: str | None, context: Any, *, ctx: "RunContext"
) -> dict[str, Any]:
    """PreToolUse hook (SDK HookCallback signature, `ctx` bound by build_hooks).

    Returns:
        A deny output for commands or scripts that could send, else an empty output.
    """
    tool_name = str(hook_input.get("tool_name", ""))
    tool_input = hook_input.get("tool_input") or {}
    code = code_text(tool_name, tool_input, ctx.run_dir)
    if not code:
        return allow()
    reason = shell_send_reason(code, ctx, is_python=is_python_file(tool_name, tool_input))
    if reason is None:
        return allow()
    return deny(reason + " Chamber runs never send; the daemon notifies the user.")
