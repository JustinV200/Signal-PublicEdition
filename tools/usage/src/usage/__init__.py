"""usage: Claude Code's 5-hour and weekly usage, and active subagents, kept in one JSON file.

Run as modules from the tool's venv python with -I (`python -I -m ...`, so
modules in the session's cwd can't shadow the stdlib), not imported by other
packages: `usage.statusline` (the status line command), `usage.hook` (the
SubagentStart and SubagentStop hook) and `usage.cli` (`usage show`). The
public contract is the state file's JSON shape, documented in
tools/usage/README.md.

Kept import-free so each entry point loads only what it uses.
"""
