# analysis_chamber.security.common

Helpers the security hooks share. Internal to `analysis_chamber.security`; nothing outside it imports this.

## Public API

- `allow()`, `deny(reason)`: PreToolUse hook outputs.
- `fail_closed(hook) -> hook`: wraps a hook so an exception inside it becomes a deny, never an allow. `build_hooks` wraps every hook with it.
- `code_text(tool_name, tool_input, base_dir) -> str | None`: the code a call runs or writes. A shell command, a Write's text for a script file (`.py .ps1 .psm1 .sh .bash .bat .cmd .ipynb`), or for Edit, MultiEdit and NotebookEdit the whole file as it will be after the edit (`edits.py`). None for anything else.
- `is_python_file(tool_name, tool_input)`: whether a file tool writes a `.py` or `.ipynb` file, whose text is Python, not shell.
- `written_path(tool_input)`, `SHELL_TOOLS`, `FILE_WRITE_TOOLS`, `SCRIPT_SUFFIXES`, `SHELL_AND_WRITE_MATCHER`.
- `split_statements(text)`: a command or script split on lines, `;`, `|`, `&&` and `||`. `split_with_breaks(text)`: the same, each paired with the break before it, so a piped statement can be told apart.
- `track_dirs(dirs, statement)` (`shell_dirs.py`): the folder stack after a statement, followed through cd, pushd/popd, Push/Pop-Location and subshells.
- `parse_shell_search(statement) -> ShellSearch | None` (`shell_search.py`): a shell search or listing (`rg`, `grep`, `findstr`, `Select-String`, `ls`, `gci`, `find`) as whether it recurses, its path words, its file-name glob and its ripgrep type.
- `path_candidates(text)`, `strip_paths(text)`, `collapse_escapes(code)`, `resolve_against(raw, base_dir)`: paths inside commands and scripts. Git Bash `/c/x` is read as `c:/x`, both in text and as a file tool's path.

## Depends on

The standard library only.
