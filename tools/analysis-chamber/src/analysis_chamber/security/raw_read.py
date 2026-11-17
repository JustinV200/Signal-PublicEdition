"""PreToolUse hook that keeps the lead and Q&A agents from reading raw Signal free text.

The agents package saves raw Signal tool output (email bodies, messages) to
<run>/data/raw/signal/ before swapping in an extract, so code can still count over it.
This hook denies Read, NotebookRead, Grep and Glob into that folder, Grep and Glob
rooted above it unless their glob or type keeps out of it (raw_search.py), and shell
commands that print or search its files: a print or search verb (cat, type,
Get-Content, jq, ...) naming the folder or reading a file after a `cd` into it, a
recursive shell search rooted at or above it (`rg invoice`, judged like Grep), and a
listing of it piped into a print verb (`gci | gc`). Python reading the files for
statistics is allowed on purpose (spec 7.2: structured counts stay exact), and so is
piping a script's output into `head`.

TODO: best effort. A Python one-liner can print a file, and paths built at run time
get through. Keeping raw Signal text outside the agents' cwd would close those gaps.
"""

import posixpath
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from analysis_chamber.guard import is_under
from analysis_chamber.security.common import (
    SHELL_TOOLS,
    allow,
    deny,
    parse_shell_search,
    resolve_against,
    split_with_breaks,
    track_dirs,
)
from analysis_chamber.security.raw_search import RAW_SIGNAL_TEXT, search_reaches_raw
from analysis_chamber.security.rules.file_verbs import PRINT_VERBS

if TYPE_CHECKING:  # type only: agents imports this package, so no runtime import back
    from analysis_chamber.agents.context import RunContext

# Must match agents.fetch.signal_swap (data/raw/ + SIGNAL_RAW_DIR).
RAW_SIGNAL_SUBDIR = Path("data") / "raw" / "signal"
READ_TOOLS = frozenset({"Read", "Grep", "Glob", "NotebookRead"})
RAW_READ_MATCHER = "|".join(sorted(READ_TOOLS | SHELL_TOOLS))

# Where a command's name sits: a statement start, after `&`, `(`, `$(` or `xargs`.
_COMMAND_START = r"^\s*(?:[&(]\s*|\$\(\s*|xargs\s+)?"
# A print verb only counts as one command's name (not `--type`, not `| head` after a
# script), with the raw path in that command's own arguments.
_PRINT_COMMAND = re.compile(_COMMAND_START + PRINT_VERBS.pattern, re.IGNORECASE)
# A print verb anywhere, as in `ForEach-Object { Get-Content $_ }` (not `--type`).
_PRINT_ANYWHERE = re.compile(r"(?<![\w-])" + PRINT_VERBS.pattern, re.IGNORECASE)
# `find ... -exec cat {} \;` prints every file find lists.
_FIND_EXEC_PRINT = re.compile(
    r"^\s*find\b.*\s-(?:exec|execdir|ok|okdir)\s+" + PRINT_VERBS.pattern, re.IGNORECASE
)
# Search verbs read the cwd (rg, grep -r) or their pattern looks like a file (`x.y`).
_SEARCH_COMMAND = re.compile(
    _COMMAND_START + r"(?:grep|rg|findstr|Select-String|sls)\b", re.IGNORECASE
)
# A file argument (`a.txt`, `*`, `.`, also before a subshell's `)`) rather than a
# count (`head -n 5` reads its stdin).
_FILE_ARGUMENT = re.compile(r"(?<!\S)(?:[*.]/?(?![^\s)])|[^\s-]\S*[.*?])")
# A piped search's quoted pattern (`| grep -c 'x.y'`), skipping its flags.
_QUOTED_PATTERN = re.compile(r"^((?:\s+-\S+)*\s+)(['\"]).*?\2")
_OFF_LIMITS = (
    "Raw Signal text in data/raw/signal/ is off limits; use the extracts you were given. "
    "Python code may read those files for counts and statistics. "
)
_READ_REASON = _OFF_LIMITS + (
    "To search or list files, pass `path` as code/, data/clean/, extracts/ or another "
    "folder outside data/raw/signal (or limit Grep to code with `type: py` or "
    "`glob: *.py`). A shell search (rg, grep -r, findstr /s, Select-String) needs a path "
    "like that too, such as `rg invoice code/ data/clean/`."
)
_LISTING_REASON = _OFF_LIMITS + (
    "A listing that reaches data/raw/signal can't be piped into a print or search "
    "command. List a folder like code/ or data/clean/ instead, or keep the listing to "
    "other files with `-Filter *.csv` (Get-ChildItem) or `-name '*.csv'` (find)."
)
# Glob characters: a path word's folder part ends before the first segment with one.
_GLOB_CHARS = re.compile(r"[*?\[]")


def _is_in_raw(current_dir: str) -> bool:
    """Whether the tracked folder is raw/signal or inside it."""
    return bool(RAW_SIGNAL_TEXT.search(current_dir + "/"))


def _names_raw(statement: str, current_dir: str) -> bool:
    """Whether a statement names raw/signal, as written or from the tracked folder.

    `cat signal/1.txt` after `cd data/raw` names it only once joined to that folder.
    """
    if RAW_SIGNAL_TEXT.search(statement):
        return True
    if _is_in_raw(current_dir):
        return False  # every word would join into it; _reads_cwd_file judges these
    words = (word.strip("'\"()").replace("\\", "/") for word in statement.split()[1:])
    return any(
        RAW_SIGNAL_TEXT.search(posixpath.normpath(posixpath.join(current_dir, word)))
        for word in words
        if word and not word.startswith("-")
    )


def _reads_cwd_file(statement: str, piped: bool) -> bool:
    """Whether a print or search statement inside raw/signal reads a file there.

    A search at a statement start reads the cwd even without a path (`rg invoice`);
    one on the right of a pipe reads stdin, so only its arguments after the quoted
    pattern count (`... | grep -c 'x.y'` is fine).
    """
    if statement.lstrip().startswith("xargs"):
        return True  # `... | xargs cat` hands cat file names
    args = _PRINT_COMMAND.sub("", statement, count=1)
    if _SEARCH_COMMAND.search(statement):
        if not piped:
            return True
        args = _QUOTED_PATTERN.sub(r"\1", args, count=1)
    return bool(_FILE_ARGUMENT.search(args))


def _covers_raw(
    statement: str, current_dir: str, ctx: "RunContext", *, piped: bool = False
) -> bool:
    """Whether a recursive shell search or listing covers raw/signal, judged like Grep.

    Each path word is split into its folder and a file-name glob (`*.txt`, `*`), so
    `findstr /s x *.txt` from the run folder reaches the raw files and
    `rg x code/` or `gci -Recurse -Filter *.csv` don't. A piped search with no path
    reads stdin, not the folder tree.
    """
    search = parse_shell_search(statement)
    if search is None or not search.is_recursive or (piped and not search.paths):
        return False
    raw_dir = ctx.run_dir / RAW_SIGNAL_SUBDIR
    for word in search.paths or (".",):
        parts = word.replace("\\", "/").split("/")
        glob_at = next((i for i, part in enumerate(parts) if _GLOB_CHARS.search(part)), None)
        folder = "/".join(parts[:glob_at]) or "."
        glob = search.glob or ("/".join(parts[glob_at:]) if glob_at is not None else "")
        root = posixpath.join(current_dir, folder)
        grep_input = {"path": root, "glob": glob, "type": search.search_type}
        if is_under(resolve_against(root, ctx.run_dir), raw_dir) or search_reaches_raw(
            "Grep", grep_input, ctx.run_dir, raw_dir
        ):
            return True
    return False


def _lists_raw(statement: str, current_dir: str, ctx: "RunContext") -> bool:
    """Whether a statement lists raw/signal's files (`ls` in it, `gci -r` above it)."""
    if parse_shell_search(statement) is None:
        return False
    is_listing_raw = _is_in_raw(current_dir) or _names_raw(statement, current_dir)
    return bool(is_listing_raw) or _covers_raw(statement, current_dir, ctx)


def _statement_reads_raw(
    statement: str, current_dir: str, *, piped: bool, ctx: "RunContext"
) -> bool:
    """Whether one statement prints or searches raw/signal text."""
    if not (_PRINT_COMMAND.search(statement) or _FIND_EXEC_PRINT.search(statement)):
        return False
    if _names_raw(statement, current_dir):
        return True
    if _is_in_raw(current_dir):
        return _reads_cwd_file(statement, piped)
    return _covers_raw(statement, current_dir, ctx, piped=piped)


def _shell_denial(command: str, ctx: "RunContext") -> str | None:
    """Why a shell command prints or searches raw/signal text, or None when it doesn't.

    The folder is followed through cd, pushd and subshells (`cd data/raw; cd signal;
    cat a.txt`); `cd ... && python x.py | head -5` is fine. A listing of the folder
    feeds every print verb later in its pipeline (`gci | gc`, `ls | xargs cat`).
    """
    dirs = ["."]
    is_fed_listing = False
    for statement_break, statement in split_with_breaks(command):
        piped = statement_break == "|"
        is_fed_listing = piped and is_fed_listing
        if is_fed_listing and _PRINT_ANYWHERE.search(statement):
            return _LISTING_REASON
        if _statement_reads_raw(statement, dirs[-1], piped=piped, ctx=ctx):
            return _READ_REASON
        is_fed_listing = is_fed_listing or _lists_raw(statement, dirs[-1], ctx)
        dirs = track_dirs(dirs, statement)
    return None


def _file_tool_reads_raw(tool_name: str, tool_input: dict[str, Any], ctx: "RunContext") -> bool:
    """Whether Read, NotebookRead, Grep or Glob is aimed into raw/signal."""
    raw_dir = ctx.run_dir / RAW_SIGNAL_SUBDIR
    paths = [
        str(tool_input[key])
        for key in ("file_path", "notebook_path", "path")
        if tool_input.get(key)
    ]
    for raw in paths:
        if RAW_SIGNAL_TEXT.search(raw) or is_under(resolve_against(raw, ctx.run_dir), raw_dir):
            return True
    # Rooted above the folder: Glob's pattern or Grep's `glob` / `type` must keep out of it.
    # Grep's `pattern` is a regex over contents, never a path.
    return search_reaches_raw(tool_name, tool_input, ctx.run_dir, raw_dir)


def raw_read_denial(tool_name: str, tool_input: dict[str, Any], ctx: "RunContext") -> str | None:
    """Why a call reads text out of <run>/data/raw/signal/, or None when it doesn't.

    Args:
        tool_name: The SDK tool name.
        tool_input: The tool's input dict.
        ctx: The run (run_dir, where relative paths start).

    Returns:
        A deny reason for a file tool aimed into the folder or a shell print or
        search of it, else None.
    """
    if tool_name in SHELL_TOOLS:
        return _shell_denial(str(tool_input.get("command") or ""), ctx)
    if tool_name in READ_TOOLS and _file_tool_reads_raw(tool_name, tool_input, ctx):
        return _READ_REASON
    return None


async def raw_read_hook(
    hook_input: dict[str, Any], tool_use_id: str | None, context: Any, *, ctx: "RunContext"
) -> dict[str, Any]:
    """PreToolUse hook (SDK HookCallback signature, `ctx` bound by build_hooks).

    Returns:
        A deny output for reads of raw Signal text, else an empty output.
    """
    tool_name = str(hook_input.get("tool_name", ""))
    reason = raw_read_denial(tool_name, hook_input.get("tool_input") or {}, ctx)
    return deny(reason) if reason else allow()
