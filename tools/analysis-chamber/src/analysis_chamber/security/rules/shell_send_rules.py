"""The shell-send hook's data: commands, imports, paths and hosts that can send.

The lead's shell can reach outbound channels without any MCP tool: gmcli (SMS), the
Signal tool CLIs (`mail send-self`, `rcs`, `sessions`, ...), the OAuth tokens behind
them, or a send API called straight from Python. Each rule is (label, pattern); a match
anywhere in a shell command or written script denies it. Python files get
PYTHON_SEND_RULES, where a CLI name only counts as a subprocess / os.system argument.
Names come from the [project.scripts] and src/ packages of tools/* and packages/*.
Update this file when a tool is added.
"""

import re

from analysis_chamber.security.common import STATEMENT_START

_CLI_NAMES = (
    "audiohub", "brief", "browser-tool", "browser-tool-visit", "calendar", "console",
    "contextmeter", "mail", "mail-digest", "assignment-check", "rcs", "sessions",
    "sleepmode", "usage", "vault", "whiteboard", "mcpshim", "gmcli", "gh",
)  # fmt: skip
_MODULE_NAMES = (
    "audiohub", "brief_tool", "browser_tool", "calendar_tool", "signal_console",
    "contextmeter", "mail_tool", "mail_digest", "rcs_tool", "claude_sessions", "sleepmode",
    "usage", "vault", "whiteboard", r"signal_\w+", "analysis_chamber", "googleauth",
    r"google\.oauth2", "google_auth_oauthlib", "googleapiclient", "twilio", "smtplib",
    "yagmail",
)  # fmt: skip

_CLI_ALTERNATION = "|".join(re.escape(name) for name in _CLI_NAMES)
_MODULE_ALTERNATION = "|".join(_MODULE_NAMES)
# Between a launcher's words: spaces, or `', '` in a Python argument list.
_WORD_BREAK = r"(?:\s+|[\"']\s*,\s*[\"'])"
# uv options that take a value, so `uv run --project tools/mail mail` finds `mail` as
# the command and `uv run python x.py --kind mail` doesn't.
_UV_VALUE_OPTIONS = (
    r"--(?:project|directory|with|with-editable|with-requirements|python|env-file|extra"
    rf"|group|only-group|no-group|package|index|from|config-file)(?:=\S+|{_WORD_BREAK}\S+)"
    r"|-[pw]\s+\S+"
)
# The words before a command: `uv run` / `uvx` and their options, in a shell command or
# a subprocess list (`['uv', 'run', 'rcs']`). `uv` alone isn't one (`print('uv sessions')`).
_UV_PREFIX = (
    rf"\b(?:uvx|uv{_WORD_BREAK}run)(?:{_WORD_BREAK}(?:{_UV_VALUE_OPTIONS}|-[\w-]+))*{_WORD_BREAK}"
)
# Python's launchers: subprocess (string or list), os.system / os.popen, and a bare
# list-form call after `from subprocess import run` (`run(['mail', 'send-self'])`).
_PYTHON_LAUNCHERS = (
    r"\bsubprocess\.\w+\(\s*\[?\s*|\bos\.(?:system|popen)\(\s*"
    r"|\b(?:run|Popen|call|check_call|check_output)\(\s*\[\s*"
)
# Launchers that run their argument as a command: Start-Process, cmd /c, powershell -c,
# bash -c, Invoke-Expression, and Python's.
_LAUNCHERS = (
    r"\bStart-Process\s+(?:-FilePath\s+)?|\bstart\s+|\bcmd(?:\.exe)?\s+/[ck]\s+"
    r"|\b(?:powershell|pwsh)(?:\.exe)?\s+(?:-\w+\s+)*?-c(?:ommand)?\s+|\b(?:ba)?sh\s+-c\s+"
    rf"|\b(?:Invoke-Expression|iex)\s+|{_PYTHON_LAUNCHERS}"
)
# Words that may come before a command in shell: `then`/`do`/`else`, wrappers that run
# their argument (`time`, `nohup`, `xargs`, `env`), and `FOO=1` assignments.
_SHELL_PREFIX_WORDS = r"(?:(?:then|do|else|xargs|env|nohup|time|\w+=\S*)\s+)*"
# A command's name may be quoted and called with `&` (`& "mail" send-self`).
_QUOTED_NAME = r"\s*(?:&\s*)?[\"']?"
# Start of a shell command: line start or after ; & | (with an optional `(` subshell),
# after `analysis-chamber gpu --`, after uv's options, or as a launcher's argument; then
# any prefix words and an optional quote. Inside `$(`, `{` or a backtick the name can't
# be quoted, so `"Done (mail $n)"`, `{ "usage $_" }` and `{ $_.mail }` aren't commands,
# and a `(` only counts at a statement start (`print('mail', 3)` isn't one).
_SHELL_COMMAND_START = (
    rf"(?:(?:(?:^|[;&|\n])\s*\(?|\bgpu\s+--\s|{_UV_PREFIX}|{_LAUNCHERS})"
    rf"\s*{_SHELL_PREFIX_WORDS}{_QUOTED_NAME}"
    rf"|(?:\$\(|[{{`])\s*{_SHELL_PREFIX_WORDS})"
)
# In Python a line start, `--` or the word `start` is just code, a SQL comment or prose
# (`usage` alone in a method chain, `print('Start mail parsing')`), so only a uv prefix
# or a subprocess / os.system argument starts a command.
_PYTHON_COMMAND_START = rf"(?:{_UV_PREFIX}|{_PYTHON_LAUNCHERS}){_QUOTED_NAME}"

_CLI_LABEL = "a Signal tool CLI"


def _cli_rule(command_start: str) -> str:
    """The Signal-CLI pattern: a CLI name where a command starts, then an argument or end."""
    return (
        rf"{command_start}(?:[\w.\\/:-]*[\\/])?(?:{_CLI_ALTERNATION})"
        # Followed by an argument or the end, so a Python line `sessions = ...` or
        # `usage.head()` isn't read as a command. A quote then a comma is a subprocess
        # argument list (['mail', 'send-self']).
        r"(?:\.exe)?(?:[\"']\s*,|[\"']?(?=[ \t]+[^\s=+\-*/%<>!:.,)\]]|[ \t]+-|\s*$|[;&|]))"
    )


# Imports at a statement start (line start, `;`, or the opening quote of
# `python -c "..."`): `import X`, `import os, X`, `from X[.y] import`; also `python -m X`
# and `importlib.import_module('X')` / `__import__('X')`. The English word "from" in
# a comment or string (`# rows from usage logs`) isn't an import.
_MODULE_RULE = (
    rf"{STATEMENT_START}(?:import\s+(?:[\w.]+\s*,\s*)*(?:{_MODULE_ALTERNATION})\b"
    rf"|from\s+(?:{_MODULE_ALTERNATION})(?:\.\w+)*\s+import\b)"
    rf"|(?<!\S)-m\s+(?:{_MODULE_ALTERNATION})\b"
    rf"|\b(?:import_module|__import__)\(\s*['\"](?:{_MODULE_ALTERNATION})\b"
)

# Rules that apply to shell and Python text alike.
_COMMON_RULES: tuple[tuple[str, str], ...] = (
    ("gmcli (SMS)", r"\bgmcli\b"),
    ("a Signal tool or Google auth module", _MODULE_RULE),
    (
        "a Signal tool or package project",
        r"--(?:project|directory|from|with-editable)[=\s]+[\"']?[^\s\"']*"
        r"(?:tools|packages)[\\/](?!analysis-chamber(?:[\"'\s]|$))",
    ),
    ("git push", r"\bgit\s+push\b"),
    (
        "a credential or state file",
        # Signal's token files: tools/*/.state (mail accounts, calendar token.bin,
        # rcs session), audiohub's .cache (Spotify token), the vault store, Claude
        # Code's login, and the usual home-folder credentials.
        r"[\\/]\.state\b|^\.state\b|(?<![\w.-])token\.(?:json|bin|pickle)\b"
        r"|spotify-token\.json|audiohub[\\/]+\.cache\b|google_client\.json"
        r"|client_secrets?[\w.-]*\.json|credentials\.json|\.credentials\b|signal-vault"
        r"|daemon\.json|\.git-credentials|[\\/]\.ssh\b|[\\/]\.aws\b|[\\/]gh[\\/]hosts\.yml"
        r"|\.npmrc\b",
    ),
    (
        "a mail, SMS or messaging send API",
        r"\bsmtp\.[\w-]|Send-MailMessage|System\.Net\.Mail|gmail\.googleapis\.com"
        r"|googleapis\.com/(?:upload/)?(?:gmail|calendar)|calendar-json\.googleapis"
        r"|oauth2\.googleapis\.com|messages\.google\.com|api\.twilio\.com"
        r"|graph\.microsoft\.com|outlook\.office|api\.sendgrid|api\.mailgun|hooks\.slack\.com"
        r"|slack\.com/api|discord(?:app)?\.com/api|api\.telegram\.org|api\.pushover\.net"
        r"|ntfy\.sh|api\.github\.com",
    ),
)


_CHAMBER_LABEL = "an analysis-chamber command other than gpu or install"
# A subcommand word after the name (not a `--flag`, not a path like
# tools\analysis-chamber --frozen), other than gpu and install. `', '` is a
# subprocess list (['analysis-chamber', 'start']).
_CHAMBER_SUBCOMMAND = (
    r"analysis-chamber(?:\.exe)?(?:[\"']\s*,\s*[\"']|[\"']?\s+)(?!(?:gpu|install)\b)[A-Za-z]"
)
# Shell: the name counts anywhere. Python has two rules so a string such as a
# User-Agent ("analysis-chamber research") isn't read as a command: one fires after
# a command start with any subcommand word, the second (below) fires anywhere but
# only on a real subcommand name.
_SHELL_CHAMBER_RULE = (_CHAMBER_LABEL, rf"\b{_CHAMBER_SUBCOMMAND}")
_PYTHON_CHAMBER_RULE = (
    _CHAMBER_LABEL,
    rf"{_PYTHON_COMMAND_START}(?:[\w.\\/:-]*[\\/])?{_CHAMBER_SUBCOMMAND}",
)
# Python also: the name anywhere, but only before a real subcommand, so a command
# held in a variable (cmd = 'analysis-chamber approve r1'; run(cmd, shell=True)) is
# caught while "analysis-chamber research (reads only)" still passes.
_PYTHON_CHAMBER_NAMED_RULE = (
    _CHAMBER_LABEL,
    r"\banalysis-chamber(?:\.exe)?(?:[\"']\s*,\s*[\"']|[\"']?\s+)"
    r"(?:serve|mcp|list|cancel|start|status|approve|ask|kit)\b",
)


def _compile(rules: tuple[tuple[str, str], ...]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Compile (label, pattern) rules, case-insensitive with ^ at every line start."""
    return tuple((label, re.compile(p, re.IGNORECASE | re.MULTILINE)) for label, p in rules)


# For shell commands and shell scripts (.ps1, .sh, .bat, ...).
SHELL_SEND_RULES = _compile(
    ((_CLI_LABEL, _cli_rule(_SHELL_COMMAND_START)), _SHELL_CHAMBER_RULE, *_COMMON_RULES)
)
# For Python files (.py, .ipynb) being written or edited.
PYTHON_SEND_RULES = _compile(
    (
        (_CLI_LABEL, _cli_rule(_PYTHON_COMMAND_START)),
        _PYTHON_CHAMBER_RULE,
        _PYTHON_CHAMBER_NAMED_RULE,
        *_COMMON_RULES,
    )
)
