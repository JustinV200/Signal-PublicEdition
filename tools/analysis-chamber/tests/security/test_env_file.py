"""Security table for env_file_hook: Signal's .env is readable by code, never edited or printed."""
# ruff: noqa: E501 -- security tables keep one case per line so they read as tables

import pytest
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import env_file_hook, shell_send_hook

# (tool name, tool input, blocked?)
ENV_TABLE = [
    ("Write", {"file_path": r"C:\work\Signal\.env", "content": "KEY=x"}, True),
    ("Edit", {"file_path": "c:/work/signal/.ENV", "old_string": "a", "new_string": "b"}, True),
    ("Write", {"file_path": ".env", "content": "x"}, False),  # the run folder's own file
    ("PowerShell", {"command": r"Add-Content C:\work\Signal\.env 'KEY=x'"}, True),
    ("PowerShell", {"command": "'KEY=x' >> $env:CHAMBER_ENV_FILE"}, True),
    ("Bash", {"command": r"echo KEY=x >> C:\work\Signal\.env"}, True),
    ("PowerShell", {"command": "Get-Content $env:CHAMBER_ENV_FILE"}, True),
    ("Bash", {"command": r"type C:\work\Signal\.env"}, True),
    ("Bash", {"command": "cat /c/work/Signal/.env"}, True),
    ("PowerShell", {"command": r"Select-String FRED C:\work\Signal\.env"}, True),
    ("PowerShell", {"command": "python code/fetch_fred.py"}, False),
    ("PowerShell", {"command": "python code/a.py > logs/a.txt  # reads key from .env"}, False),
    ("PowerShell", {"command": r"uv run --env-file C:\work\Signal\.env python code/a.py"}, False),
    ("Bash", {"command": "python -c \"import os; print(len(os.environ))\""}, False),
    # Inline code or a script that prints the whole file; reading one key stays allowed.
    ("Bash", {"command": "python -c \"print(open(r'C:\\Work\\Signal\\.env').read())\""}, True),
    ("PowerShell", {"command": "python -c \"import os; print(open(os.environ['CHAMBER_ENV_FILE']).read())\""}, True),
    ("Write", {"file_path": "code/k.py", "content": "print(Path(os.environ['CHAMBER_ENV_FILE']).read_text())"}, True),
    ("Write", {"file_path": "code/k.py", "content": "key = dotenv_values(os.environ['CHAMBER_ENV_FILE'])['FRED_API_KEY']\nprint(df.head())"}, False),
]  # fmt: skip

# Reading .env from code must not trip the shell-send credential rules.
ENV_READS = [
    ("Write", {"file_path": "code/keys.py", "content": "from dotenv import dotenv_values\nkey = dotenv_values(os.environ['CHAMBER_ENV_FILE'])['FRED_API_KEY']"}),
    ("Write", {"file_path": "code/keys.py", "content": "open(r'C:\\Work\\Signal\\.env').read()"}),
    ("PowerShell", {"command": r"uv run --env-file C:\work\Signal\.env python code/a.py"}),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "tool_input", "blocked"), ENV_TABLE)
async def test_env_file_hook(make_ctx, tool: str, tool_input: dict, blocked: bool) -> None:
    output = await env_file_hook(hook_input(tool, **tool_input), "u", {}, ctx=make_ctx(False))
    assert is_deny(output) is blocked


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "tool_input"), ENV_READS)
async def test_reading_env_from_code_is_not_a_send(make_ctx, tool: str, tool_input: dict) -> None:
    output = await shell_send_hook(hook_input(tool, **tool_input), "u", {}, ctx=make_ctx(False))
    assert not is_deny(output)
