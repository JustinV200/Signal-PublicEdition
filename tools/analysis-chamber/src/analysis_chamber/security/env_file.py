"""PreToolUse hook guarding Signal's .env: code may read it, agents may not edit or print it.

The lead's Python reads API keys from <repo_root>/.env (its path is in env
CHAMBER_ENV_FILE); only the chamber's own code (chamber_get_api_key) appends to it.
This hook denies Write/Edit/MultiEdit/NotebookEdit of that file; shell commands that
name it (or $env:CHAMBER_ENV_FILE) with a write verb, a redirect into it, or a verb that
prints it (cat, type, Get-Content, grep, ...); and inline code or scripts that print
the whole file (`print(open(...).read())`), so keys never land in the transcript.
Reading one key by name stays allowed.

TODO: best effort. A script can still print a key it read, or loop over the file and
print each line; that's the intended read path, so only whole-file prints are caught.
"""

import re
from typing import TYPE_CHECKING, Any

from analysis_chamber.guard import is_under
from analysis_chamber.security.common import (
    FILE_WRITE_TOOLS,
    SHELL_TOOLS,
    allow,
    code_text,
    deny,
    resolve_against,
    strip_paths,
    written_path,
)
from analysis_chamber.security.rules.file_verbs import PRINT_VERBS, SHELL_REDIRECT, WRITE_MARKERS

if TYPE_CHECKING:  # type only: agents imports this package, so no runtime import back
    from analysis_chamber.agents.context import RunContext

ENV_FILE_NAME = ".env"
# `.env` as a file name (not .environ / .envrc), or the variable that holds its path.
_ENV_MENTION = re.compile(r"\.env(?![\w.-])|CHAMBER_ENV_FILE", re.IGNORECASE)
# uv's `--env-file .env` only loads it into a process; drop it before checking verbs.
_ENV_FILE_FLAG = re.compile(r"--env-file[=\s]+\S+", re.IGNORECASE)
# A print call wrapping a whole-file read on the same line: print(open(p).read()),
# print(Path(p).read_text()), pprint(dotenv_values(p)), Write-Output ...ReadAllText.
_WHOLE_FILE_PRINT = re.compile(
    r"\b(?:print|pprint|Write-(?:Output|Host))\b[^\n]*?(?:\.read\(\s*\)|\.read_text\("
    r"|\.readlines\(|\bdotenv_values\([^\n]*?\)(?!\s*\[)|ReadAll(?:Text|Lines)\()",
    re.IGNORECASE,
)


def _shell_touches_env(command: str) -> bool:
    """Whether a shell command names .env with a write or print verb, or redirects into it."""
    command = _ENV_FILE_FLAG.sub(" ", command)
    if not _ENV_MENTION.search(command):
        return False
    verbs_text = strip_paths(command)
    if WRITE_MARKERS.search(verbs_text) or PRINT_VERBS.search(verbs_text):
        return True
    # Only a redirect into .env counts, not `> logs/a.txt  # key from .env`.
    return any(_ENV_MENTION.search(m.group(1)) for m in SHELL_REDIRECT.finditer(command))


def is_env_touch(tool_name: str, tool_input: dict[str, Any], ctx: "RunContext") -> bool:
    """Whether a call would change or print <repo_root>/.env.

    Args:
        tool_name: The SDK tool name.
        tool_input: The tool's input dict.
        ctx: The run (run_dir for relative paths, config.repo_root).

    Returns:
        True for a file edit of .env, a shell command naming .env with a write or
        print verb, or a command or script that prints the whole file.

    Raises:
        OSError: An edited script exists but can't be read.
    """
    if tool_name in FILE_WRITE_TOOLS:
        target = written_path(tool_input)
        env_path = ctx.config.repo_root / ENV_FILE_NAME
        if target and is_under(resolve_against(target, ctx.run_dir), env_path):
            return True
    if tool_name in SHELL_TOOLS and _shell_touches_env(str(tool_input.get("command") or "")):
        return True
    code = code_text(tool_name, tool_input, ctx.run_dir) or ""
    return bool(_ENV_MENTION.search(code) and _WHOLE_FILE_PRINT.search(code))


async def env_file_hook(
    hook_input: dict[str, Any], tool_use_id: str | None, context: Any, *, ctx: "RunContext"
) -> dict[str, Any]:
    """PreToolUse hook (SDK HookCallback signature, `ctx` bound by build_hooks).

    Returns:
        A deny output for edits or prints of .env, else an empty output.
    """
    tool_name = str(hook_input.get("tool_name", ""))
    if is_env_touch(tool_name, hook_input.get("tool_input") or {}, ctx):
        return deny(
            "Signal's .env is read-only and never printed. Read the key you need in Python "
            "(path in env CHAMBER_ENV_FILE); use chamber_get_api_key to store a new one."
        )
    return allow()
