"""Helpers every chamber security hook shares: hook outputs, tool-input text and paths."""

from analysis_chamber.security.common.code_paths import (
    collapse_escapes,
    path_candidates,
    resolve_against,
    strip_paths,
)
from analysis_chamber.security.common.decisions import SecurityHook, allow, deny, fail_closed
from analysis_chamber.security.common.shell_dirs import track_dirs
from analysis_chamber.security.common.shell_search import ShellSearch, parse_shell_search
from analysis_chamber.security.common.statements import (
    STATEMENT_START,
    split_statements,
    split_with_breaks,
)
from analysis_chamber.security.common.tool_text import (
    FILE_WRITE_TOOLS,
    SCRIPT_SUFFIXES,
    SHELL_AND_WRITE_MATCHER,
    SHELL_TOOLS,
    code_text,
    is_python_file,
    written_path,
)

__all__ = [
    "FILE_WRITE_TOOLS",
    "SCRIPT_SUFFIXES",
    "SHELL_AND_WRITE_MATCHER",
    "SHELL_TOOLS",
    "STATEMENT_START",
    "SecurityHook",
    "ShellSearch",
    "allow",
    "code_text",
    "collapse_escapes",
    "deny",
    "fail_closed",
    "is_python_file",
    "parse_shell_search",
    "path_candidates",
    "resolve_against",
    "split_statements",
    "split_with_breaks",
    "strip_paths",
    "track_dirs",
    "written_path",
]
