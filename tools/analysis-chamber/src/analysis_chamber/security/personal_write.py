"""PreToolUse hook that stops a personal run writing anywhere under the Signal repo.

Spec 13 / decision 48: a run whose manifest isn't explicitly non-personal (personal
True or still None) can't write under config.repo_root, so personal data never lands
in life/ or anywhere git could pick it up. File tools are checked exactly with
guard.is_under (resolves `..`, links and case; Git Bash /c/x paths too). Shell commands
and script files are best effort, one statement (line, `;`, `|`, `&&`) at a time: a
statement that names a repo path and writes is denied, except a copy whose destination
(its last argument) is outside the repo. `--out <repo path>` style arguments are denied
anywhere, and so is a shell redirect (`> x`) whose target is in the repo. So reading
life/ and writing into the run folder stays allowed, and `>` in Python is a comparison.

TODO: best-effort gaps for shell and scripts: a repo path in a variable on one line and
the write on another, paths built at run time, env vars ($env:USERPROFILE...), `cd`
into the repo in one call and a relative write in the next, and writes through
programs whose names aren't in WRITE_MARKERS. A one-line read from the repo and write
into the run folder (`pd.read_csv(repo_path).to_csv('data/x.csv')`) is one statement
that names a repo path and writes, so it's still denied: split it over two lines.
"""

import re
from typing import TYPE_CHECKING, Any

from analysis_chamber.guard import is_under
from analysis_chamber.security.common import (
    FILE_WRITE_TOOLS,
    allow,
    code_text,
    collapse_escapes,
    deny,
    is_python_file,
    path_candidates,
    resolve_against,
    split_statements,
    strip_paths,
    written_path,
)
from analysis_chamber.security.rules.file_verbs import SHELL_REDIRECT, WRITE_MARKERS

if TYPE_CHECKING:  # type only: agents imports this package, so no runtime import back
    from analysis_chamber.agents.context import RunContext

# Copy commands whose last argument is the destination; a read-only source may be in
# the repo. robocopy and Move-Item aren't here: robocopy's last word may be a file
# filter, and a move deletes the repo source.
_COPY_COMMAND = re.compile(r"^\s*(?:&\s*)?(?:cp|copy|Copy-Item|cpi|xcopy)\b", re.IGNORECASE)
_ARGUMENT = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")
# Output-path options of scripts and cmdlets (`--out x`, `-o x`, `-OutFile x`).
_OUTPUT_OPTION = re.compile(
    r"(?<!\S)--?(?:o|out|output|outfile|out-file|outdir|out-dir|output-dir|output-file"
    r"|dest|destination|save|save-to|target|to|write)(?:=|\s+)(\"[^\"]*\"|'[^']*'|\S+)",
    re.IGNORECASE,
)


def _in_repo(raw_path: str, ctx: "RunContext") -> bool:
    """Whether a raw path (quotes allowed, relative to the run folder) is under the repo."""
    path = raw_path.strip("'\"")
    return bool(path) and is_under(resolve_against(path, ctx.run_dir), ctx.config.repo_root)


def _last_argument(statement: str) -> str:
    """A command's last non-flag argument (a copy's destination), or ""."""
    arguments = [word for word in _ARGUMENT.findall(statement)[1:] if not word.startswith("-")]
    return arguments[-1] if arguments else ""


def _statement_writes_repo(statement: str, ctx: "RunContext") -> bool:
    """Whether one statement names a repo path and writes, other than copying out of it."""
    if not any(_in_repo(raw, ctx) for raw in path_candidates(statement)):
        return False
    if not WRITE_MARKERS.search(strip_paths(statement)):
        return False
    if _COPY_COMMAND.match(statement):
        # A redirect's target isn't the copy's destination; redirects are checked apart.
        return _in_repo(_last_argument(SHELL_REDIRECT.sub(" ", statement)), ctx)
    return True


def _redirects_into_repo(text: str, ctx: "RunContext") -> bool:
    """Whether a shell redirect (`> x`, `>> x`, `2> x`) targets a repo path."""
    return any(_in_repo(match.group(1), ctx) for match in SHELL_REDIRECT.finditer(text))


def is_repo_write(tool_name: str, tool_input: dict[str, Any], ctx: "RunContext") -> bool:
    """Whether a tool call would write under ctx.config.repo_root.

    Args:
        tool_name: The SDK tool name.
        tool_input: The tool's input dict.
        ctx: The run (run_dir for relative paths, config.repo_root).

    Returns:
        True for a file write into the repo, an output option naming a repo path, or a
        shell or script statement that names a repo path and writes into it.

    Raises:
        OSError: An edited script exists but can't be read.
    """
    target = written_path(tool_input) if tool_name in FILE_WRITE_TOOLS else None
    if target and _in_repo(target, ctx):
        return True
    code = code_text(tool_name, tool_input, ctx.run_dir)
    if not code:
        return False
    text = collapse_escapes(code)
    if any(_in_repo(match.group(1), ctx) for match in _OUTPUT_OPTION.finditer(text)):
        return True
    # `>` is a comparison in Python, so only shell text has its redirects checked.
    if not is_python_file(tool_name, tool_input) and _redirects_into_repo(text, ctx):
        return True
    return any(_statement_writes_repo(part, ctx) for part in split_statements(text))


async def personal_write_hook(
    hook_input: dict[str, Any], tool_use_id: str | None, context: Any, *, ctx: "RunContext"
) -> dict[str, Any]:
    """PreToolUse hook (SDK HookCallback signature, `ctx` bound by build_hooks).

    build_hooks only adds it when ctx.manifest.personal is not False; it checks the
    flag again so a stale binding can't let a personal run through.

    Returns:
        A deny output for writes under the repo, else an empty output.
    """
    if ctx.manifest.personal is False:
        return allow()
    tool_name = str(hook_input.get("tool_name", ""))
    if is_repo_write(tool_name, hook_input.get("tool_input") or {}, ctx):
        return deny(
            "This is a personal run: nothing may be written under "
            f"{ctx.config.repo_root}. Keep every file in the run folder {ctx.run_dir}."
        )
    return allow()
