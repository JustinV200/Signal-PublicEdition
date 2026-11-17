"""Security table for raw_read_hook: no reading raw Signal free text from data/raw/signal/."""
# ruff: noqa: E501 -- security tables keep one case per line so they read as tables

import pytest
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import raw_read_hook

# (tool name, tool input, blocked?). Relative paths are run-folder relative.
RAW_READ_TABLE = [
    ("Read", {"file_path": "data/raw/signal/mail_read-1.json"}, True),
    ("Read", {"file_path": r"data\raw\signal\x.json"}, True),
    ("Read", {"file_path": "data/raw/fred.csv"}, False),
    ("Read", {"file_path": "extracts/mail-1.json"}, False),
    ("NotebookRead", {"notebook_path": "data/raw/signal/n.ipynb"}, True),
    ("Grep", {"pattern": "invoice", "path": "data/raw/signal"}, True),
    ("Grep", {"pattern": "def ", "path": "code"}, False),
    ("Glob", {"pattern": "data/raw/signal/*.json"}, True),
    ("Glob", {"pattern": "data/raw/**/*.txt"}, True),
    ("Glob", {"pattern": "data/raw/*.csv"}, False),
    ("Glob", {"pattern": "*.json", "path": "data/raw/signal"}, True),
    ("PowerShell", {"command": r"Get-Content data\raw\signal\mail_read-1.json"}, True),
    ("PowerShell", {"command": r"gc .\data\raw\signal\x.json | Select-Object -First 5"}, True),
    ("Bash", {"command": "cat data/raw/signal/*.json"}, True),
    ("Bash", {"command": "type data\\raw\\signal\\x.json"}, True),
    ("Bash", {"command": "python code/count.py data/raw/signal"}, False),  # code may count
    ("Bash", {"command": "cat data/raw/fred.csv"}, False),
    ("Write", {"file_path": "code/count.py", "content": "open('data/raw/signal/x.json')"}, False),
    ("Bash", {"command": "python code/count.py data/raw/signal | head -5"}, False),
    ("Bash", {"command": "python code/count.py data/raw/signal --type json"}, False),
    ("Read", {"file_path": "data/raw/signal.csv"}, False),  # a file, not the folder
    ("Glob", {"pattern": "**/signal/*"}, True),
    ("Glob", {"pattern": "data/*/signal/*.txt"}, True),
    ("Glob", {"pattern": "**/*.py"}, False),
    ("Grep", {"pattern": "data/raw/signal", "path": "code"}, False),  # a regex, not a path
    ("Grep", {"pattern": "invoice", "glob": "data/raw/signal/*.json"}, True),
    ("Grep", {"pattern": "invoice", "path": "code", "glob": "*.py"}, False),
    # Searches rooted above the folder reach it unless limited to code or other folders.
    ("Grep", {"pattern": "invoice"}, True),
    ("Grep", {"pattern": "invoice", "path": "data", "output_mode": "content"}, True),
    ("Grep", {"pattern": "invoice", "path": "data", "glob": "*.txt"}, True),
    ("Grep", {"pattern": "def ", "type": "py"}, False),
    ("Grep", {"pattern": "def ", "glob": "**/*.{py,ipynb}"}, False),
    ("Grep", {"pattern": "invoice", "path": "extracts"}, False),
    ("Grep", {"pattern": "x", "glob": "data/clean/*.csv"}, False),
    ("Glob", {"pattern": "**/*"}, True),
    ("Glob", {"pattern": "figures/**/*.png"}, False),
    # Raw files are always .txt, so a glob or type for other files keeps out of them.
    ("Grep", {"pattern": "price", "glob": "*.csv"}, False),
    ("Grep", {"pattern": "x", "glob": "*"}, True),
    ("Grep", {"pattern": "x", "glob": "!*.csv"}, True),
    ("Grep", {"pattern": "x", "glob": "*.{csv,txt}"}, True),
    ("Grep", {"pattern": "x", "type": "py", "glob": "*.txt"}, True),  # rg's -g overrides -t
    ("Bash", {"command": "jq . data/raw/signal/a.json"}, True),
    ("Bash", {"command": "python -m json.tool data/raw/signal/a.json"}, True),
    ("Bash", {"command": "cd data/raw/signal && cat a.txt"}, True),
    ("Bash", {"command": "cd data/raw/signal; cd ../../clean; cat a.csv"}, False),
    ("Bash", {"command": "(cd data/raw; cd signal && cat a.txt)"}, True),
    ("Bash", {"command": "cd data/raw/signal && python ../../../code/count.py | head -5"}, False),
    # Inside the folder a bare `*` or `.` is a file, and a search reads the cwd.
    ("Bash", {"command": "cd data/raw/signal && cat *"}, True),
    ("PowerShell", {"command": "Set-Location data/raw/signal; Get-Content -Path *"}, True),
    ("Bash", {"command": "cd data/raw/signal && grep -r x ."}, True),
    ("Bash", {"command": "cd data/raw/signal && rg invoice"}, True),
    ("Bash", {"command": "cd data/raw/signal && python ../../../code/a.py | grep -c 'x.y'"}, False),
    ("Bash", {"command": "cd data/raw/signal && python a.py | grep 'x' a.txt"}, True),
    ("Bash", {"command": "cd data/raw/signal && ls | xargs cat"}, True),
    # Leaving: a subshell's end or popd / Pop-Location; popd with nothing pushed stays put.
    ("Bash", {"command": "(cd data/raw/signal && ls | wc -l); head -5 data/clean/x.csv"}, False),
    ("PowerShell", {"command": r"Push-Location data/raw/signal; python ..\..\..\code\count.py; Pop-Location; Get-Content data/clean/x.csv -TotalCount 3"}, False),
    ("Bash", {"command": "pushd data/raw/signal; popd; cat data/clean/x.csv"}, False),
    ("Bash", {"command": "cd data/raw/signal; popd; cat a.txt"}, True),
    ("PowerShell", {"command": "Push-Location data; Push-Location raw/signal; Pop-Location; Push-Location raw/signal; gc a.txt"}, True),
    ("PowerShell", {"command": "cd data/raw/signal; $n = (Get-ChildItem | Measure-Object).Count; cat a.txt"}, True),
    ("Bash", {"command": "(cd data/raw/signal && cat *)"}, True),
    # A listing of the folder piped into a print verb hands it the file names.
    ("PowerShell", {"command": "cd data/raw/signal; gci | gc"}, True),
    ("PowerShell", {"command": "Get-ChildItem data/raw/signal | ForEach-Object { Get-Content $_ }"}, True),
    ("PowerShell", {"command": "Get-ChildItem -Recurse | Select-String invoice"}, True),
    ("Bash", {"command": "ls data/raw/signal | xargs cat"}, True),
    ("Bash", {"command": "cd data/raw/signal && ls | wc -l"}, False),
    # Recursive shell searches from at or above the folder reach it, as Grep with no path does.
    ("Bash", {"command": "rg invoice"}, True),
    ("Bash", {"command": "grep -r x ."}, True),
    ("Bash", {"command": "cd code; grep -rn invoice .."}, True),
    ("PowerShell", {"command": "Select-String -Path * -Recurse -Pattern invoice"}, True),
    ("PowerShell", {"command": "findstr /s /i invoice *.txt"}, True),
    ("Bash", {"command": "rg invoice data"}, True),
    ("Bash", {"command": "rg invoice code/ data/clean/"}, False),
    ("Bash", {"command": "rg -t py invoice"}, False),
    ("Bash", {"command": "grep -r --include=*.csv x ."}, False),
    ("PowerShell", {"command": "Get-ChildItem -Recurse -Filter *.csv | Select-String x"}, False),
    ("Bash", {"command": "grep x *.csv"}, False),  # not recursive: run-folder files only
    ("Bash", {"command": "python code/a.py | rg invoice"}, False),  # reads stdin
    ("Bash", {"command": "rg --files code"}, False),  # no pattern: code is the path
    ("Bash", {"command": "cd data/raw; cat signal/1.txt"}, True),
    ("Bash", {"command": "find data -name '*.txt' -exec cat {} \\;"}, True),
    ("Bash", {"command": "find code -exec cat {} \\;"}, False),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "tool_input", "blocked"), RAW_READ_TABLE)
async def test_raw_read_hook(make_ctx, tool: str, tool_input: dict, blocked: bool) -> None:
    output = await raw_read_hook(hook_input(tool, **tool_input), "u", {}, ctx=make_ctx(False))
    assert is_deny(output) is blocked
