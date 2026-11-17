"""Security table for personal_write_hook: personal runs never write under the repo."""
# ruff: noqa: E501 -- security tables keep one case per line so they read as tables

import pytest
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import personal_write_hook

# (tool name, tool input, blocked for a personal run?). Relative paths are run-folder
# relative; the run folder is under tmp_path, outside the repo.
WRITE_TABLE = [
    ("Write", {"file_path": r"C:\work\Signal\life\a.md", "content": "x"}, True),
    ("Write", {"file_path": r"c:\work\SIGNAL\life\a.md", "content": "x"}, True),
    ("Write", {"file_path": "C:/Work/Signal/life/a.md", "content": "x"}, True),
    ("Write", {"file_path": r"C:\work\Other\..\Signal\life\a.md", "content": "x"}, True),
    ("Edit", {"file_path": r"C:\work\Signal\tools\x.py", "old_string": "a", "new_string": "b"}, True),
    ("NotebookEdit", {"notebook_path": r"C:\work\Signal\n.ipynb", "new_source": "1"}, True),
    ("Write", {"file_path": "report.md", "content": "x"}, False),
    ("Write", {"file_path": r"C:\work\Signal-private\a.md", "content": "x"}, False),
    ("Bash", {"command": r"echo x > C:\work\Signal\life\a.md"}, True),
    ("Bash", {"command": "cp out.csv /c/work/Signal/life/"}, True),
    ("PowerShell", {"command": r"Set-Content -Path C:\work\Signal\life\a.md -Value x"}, True),
    ("PowerShell", {"command": r"'x' | Out-File 'C:\work\Signal\life\a.md'"}, True),
    ("PowerShell", {"command": r"Get-Content C:\work\Signal\life\a.md"}, False),  # read only
    ("PowerShell", {"command": r"Get-Content C:\work\Signal\x.md 2>$null"}, False),
    ("PowerShell", {"command": "Set-Content report.md x"}, False),
    ("Write", {"file_path": "code/w.py", "content": "open(r'C:\\Work\\Signal\\life\\a.md', 'w')"}, True),
    ("Write", {"file_path": "code/w.py", "content": "df.to_csv('C:\\\\Work\\\\Signal\\\\life\\\\t.csv')"}, True),
    ("Write", {"file_path": "code/w.py", "content": "df.to_csv('data/clean/t.csv')"}, False),
    ("Write", {"file_path": "/c/work/Signal/life/a.md", "content": "x"}, True),  # Git Bash path
    ("Bash", {"command": r"git -C C:\work\Signal add life/a.md"}, True),
    ("PowerShell", {"command": r"python code/a.py --in C:\work\Signal\life\x.csv --out C:\work\Signal\life\y.csv"}, True),
    ("PowerShell", {"command": r"iwr https://example.org/x.csv -OutFile C:\work\Signal\life\x.csv"}, True),
    # Reading from the repo and writing into the run folder is fine.
    ("PowerShell", {"command": r"Get-Content C:\work\Signal\life\a.md | Set-Content notes.md"}, False),
    ("PowerShell", {"command": r"Copy-Item C:\work\Signal\life\x.csv data\raw\ "}, False),
    ("PowerShell", {"command": r"python code/a.py C:\work\Signal\life\x.csv --out data/y.csv"}, False),
    ("PowerShell", {"command": r"python code/a.py C:\work\Signal\life\a.md report.md"}, False),
    ("Write", {"file_path": "code/w.py", "content": "df = pd.read_csv(r'C:\\Work\\Signal\\life\\x.csv')\ndf.to_csv('data/clean/x.csv')"}, False),
    # `>` is a comparison in Python; in shell only a redirect into the repo counts.
    ("PowerShell", {"command": r"python code/a.py C:\work\Signal\life\x.csv > logs/a.txt"}, False),
    ("Bash", {"command": r"python code/a.py > C:\work\Signal\life\out.txt"}, True),
    ("Write", {"file_path": "code/w.py", "content": "df = pd.read_csv(r'C:\\Work\\Signal\\life\\x.csv')[lambda d: d.n > 0]  # -> data/clean"}, False),
    ("Write", {"file_path": "code/w.py", "content": "pd.read_csv(r'C:\\Work\\Signal\\life\\x.csv').to_csv('data/clean/x.csv')"}, True),  # one line: still denied
    ("PowerShell", {"command": r"[IO.File]::WriteAllText('C:\work\Signal\life\a.md', 'x')"}, True),
    # An edit is checked against the whole script after it (files in conftest).
    ("Edit", {"file_path": "code/old_write.py", "old_string": "data/clean/t.csv", "new_string": r"C:\work\Signal\life\t.csv"}, True),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "tool_input", "blocked"), WRITE_TABLE)
async def test_personal_write_hook(make_ctx, tool: str, tool_input: dict, blocked: bool) -> None:
    output = await personal_write_hook(hook_input(tool, **tool_input), "u", {}, ctx=make_ctx(True))
    assert is_deny(output) is blocked
