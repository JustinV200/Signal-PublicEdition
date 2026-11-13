"""contextmeter: tells every agent, subagents included, how full its context window is.

Run as `python -I -m contextmeter.hook` from the tool's venv; it's a Claude Code
PostToolUse hook, not a library. Kept import-free so the hook loads only what it uses.
"""
