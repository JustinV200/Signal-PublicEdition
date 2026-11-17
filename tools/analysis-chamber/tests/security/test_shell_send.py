"""Security table for shell_send_hook: no sends around the MCP block."""
# ruff: noqa: E501 -- security tables keep one case per line so they read as tables

import pytest
from support.security_hooks import hook_input, is_deny

from analysis_chamber.security import shell_send_hook

# (tool name, tool input, blocked?)
SHELL_TABLE = [
    ("PowerShell", {"command": "gmcli send --to 555 hi"}, True),
    ("PowerShell", {"command": "& $env:APPDATA\\gmcli\\gmcli.exe messages"}, True),
    ("Bash", {"command": "mail send-self --file r.txt"}, True),
    ("Bash", {"command": "cd x && rcs read"}, True),
    ("PowerShell", {"command": "uv run --project tools/mail --frozen mail send-self"}, True),
    ("PowerShell", {"command": r"uv run --directory C:\work\Signal --project tools\sessions sessions start"}, True),
    ("PowerShell", {"command": r"& C:\work\Signal\tools\rcs\.venv\Scripts\rcs.exe status"}, True),
    ("Bash", {"command": "python -m mail_tool.cli send-self"}, True),
    ("Bash", {"command": "git push origin main"}, True),
    ("Bash", {"command": "gh issue create -t x"}, True),
    ("Bash", {"command": r"type C:\work\Signal\tools\mail\.state\accounts\personal.bin"}, True),
    ("Bash", {"command": "cat google_client.json"}, True),
    ("Bash", {"command": "python -c \"open('token.json').read()\""}, True),
    ("Bash", {"command": r"dir %LOCALAPPDATA%\signal-vault"}, True),
    ("PowerShell", {"command": "Send-MailMessage -To a@b.c -SmtpServer smtp.gmail.com"}, True),
    ("Bash", {"command": "curl https://api.twilio.com/2010-04-01/Accounts/x/Messages.json"}, True),
    ("Write", {"file_path": "code/s.py", "content": "import smtplib\nsmtplib.SMTP('smtp.gmail.com')"}, True),
    ("Write", {"file_path": "code/s.py", "content": "from google.oauth2.credentials import Credentials"}, True),
    ("Write", {"file_path": "code/s.py", "content": "requests.post('https://gmail.googleapis.com/gmail/v1/users/me/messages/send')"}, True),
    ("PowerShell", {"command": "analysis-chamber start 'q'"}, True),
    ("PowerShell", {"command": r"uv run --project C:\work\Signal\tools\analysis-chamber --frozen analysis-chamber gpu -- python code/train.py"}, False),
    ("PowerShell", {"command": "analysis-chamber gpu -- mail send-self"}, True),
    ("PowerShell", {"command": r"uv pip install --python .venv\Scripts\python.exe polars==1.0"}, False),
    ("Bash", {"command": "python code/analyse.py --emails 120"}, False),
    ("Write", {"file_path": "code/a.py", "content": "api_key = os.environ['FRED_API_KEY']\nprint(df.describe())"}, False),
    ("Write", {"file_path": "code/a.py", "content": "sessions = df.groupby('id')\nusage.head()\nprint(len(mail))"}, False),
    ("Write", {"file_path": "code/a.py", "content": "import subprocess\nsubprocess.run('gmcli send x', shell=True)"}, True),
    # The chamber's own commands and folder.
    ("PowerShell", {"command": "analysis-chamber install shap umap-learn"}, False),
    ("PowerShell", {"command": "analysis-chamber --help"}, False),
    ("Write", {"file_path": "code/a.py", "content": "UA = {'User-Agent': 'analysis-chamber research (reads only)'}"}, False),  # live run 3
    ("Write", {"file_path": "code/a.py", "content": "import subprocess\nsubprocess.run(['analysis-chamber', 'start', 'q'])"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import os\nos.system('uv run --project tools/analysis-chamber analysis-chamber ask x y')"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import subprocess\nsubprocess.run(['analysis-chamber', 'gpu', '--', 'python', 't.py'])"}, False),
    ("Write", {"file_path": "code/a.py", "content": "cmd = 'analysis-chamber approve r1 --personal yes'\nsubprocess.run(cmd, shell=True)"}, True),
    ("PowerShell", {"command": r"& C:\work\Signal\tools\analysis-chamber\.venv\Scripts\analysis-chamber.exe gpu -- python code/t.py"}, False),
    ("PowerShell", {"command": r"Get-Content C:\work\Signal\tools\analysis-chamber\skills\playbook\gpu-and-installs.md"}, False),
    ("PowerShell", {"command": r"type C:\work\Signal\tools\analysis-chamber\.state\daemon.json"}, True),
    ("Write", {"file_path": "code/a.py", "content": "from analysis_chamber.notify import Notifier"}, True),
    # Words after `uv run python` are arguments, not commands.
    ("PowerShell", {"command": "uv run python code/a.py --kind mail --source rcs"}, False),
    ("PowerShell", {"command": "uv run --frozen --with polars mail send-self"}, True),
    # Launchers that run a Signal CLI.
    ("PowerShell", {"command": "Start-Process mail -ArgumentList send-self"}, True),
    ("Bash", {"command": "cmd /c \"mail send-self --file r.txt\""}, True),
    ("PowerShell", {"command": "powershell -NoProfile -Command 'rcs read'"}, True),
    # Wrapped in a group, a block or a prefix word.
    ("Bash", {"command": "(mail send-self)"}, True),
    ("Bash", {"command": "if true; then mail send-self; fi"}, True),
    ("Bash", {"command": "FOO=1 nohup mail send-self &"}, True),
    ("PowerShell", {"command": "Import-Csv data/clean/x.csv | ForEach-Object { $_.mail }"}, False),
    ("PowerShell", {"command": "if ($x) { mail send-self }"}, True),
    # A `(` or `{` inside a string isn't a command start.
    ("Bash", {"command": "python -c \"print('mail stats', 3)\""}, False),
    ("PowerShell", {"command": "Write-Host \"Done (mail $n)\"; python code/a.py | ForEach-Object { \"usage $_\" }"}, False),
    ("Write", {"file_path": "code/a.py", "content": "import subprocess\nsubprocess.run(['mail', 'send-self'])"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import os\nos.system('sessions start x')"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import subprocess\nsubprocess.Popen(['uv', 'run', 'rcs', 'send'])"}, True),
    ("Write", {"file_path": "code/a.py", "content": "from subprocess import run\nrun(['mail', 'send-self'])"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import subprocess\nsubprocess.run(['uv', 'run', 'python', 'code/b.py', '--kind', 'mail'])"}, False),
    # Token files by name: Signal's, not every file with "token" in it.
    ("Bash", {"command": "cat C:/Users/x/AppData/Local/audiohub/spotify-token.json"}, True),
    ("Bash", {"command": "cat models/bert/tokenizer.json"}, False),
    ("Write", {"file_path": "code/a.py", "content": "cfg = json.load(open('models/bert/tokenizer_config.json'))"}, False),
    ("Write", {"file_path": "code/a.py", "content": "usage = pd.read_json('data/clean/token_usage.json')"}, False),
    # In Python a bare CLI word on its own line, a SQL `--` comment or `start` is code.
    ("Write", {"file_path": "code/a.py", "content": "counts = (\n    usage\n    .groupby('day')\n    .size()\n)"}, False),
    ("Write", {"file_path": "code/a.py", "content": "rows = [\n    mail\n    for mail in batch\n]"}, False),
    ("NotebookEdit", {"notebook_path": "code/new.ipynb", "new_source": "usage = df.groupby('d').size()\nusage", "edit_mode": "insert"}, False),
    ("Write", {"file_path": "code/a.py", "content": "q = '''\nSELECT d, count(*) -- mail volume per day\nFROM t\n'''"}, False),
    ("Write", {"file_path": "code/a.py", "content": "print('Start mail parsing')"}, False),
    ("Write", {"file_path": "code/s.ps1", "content": "Write-Host hi\nmail send-self --file r.txt"}, True),  # shell script
    # Imports at a statement start only; the word "from" in prose isn't one.
    ("Write", {"file_path": "code/a.py", "content": "# cost from usage logs\nax.set_title('tokens from usage')"}, False),
    ("Write", {"file_path": "code/a.py", "content": "from mail_tool.cli import main"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import os, smtplib"}, True),
    ("Write", {"file_path": "code/a.py", "content": "import importlib\nm = importlib.import_module('mail_tool')"}, True),
    ("Write", {"file_path": "code/a.py", "content": "__import__('smtplib')"}, True),
    # An edit is checked against the whole script after it (files in conftest).
    ("Edit", {"file_path": "code/old_send.py", "old_string": "echo", "new_string": "mail"}, True),
]  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "tool_input", "blocked"), SHELL_TABLE)
async def test_shell_send_hook(make_ctx, tool: str, tool_input: dict, blocked: bool) -> None:
    output = await shell_send_hook(hook_input(tool, **tool_input), "u", {}, ctx=make_ctx(False))
    assert is_deny(output) is blocked
