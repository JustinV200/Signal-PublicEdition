"""Public API of signal_console.setup_cli: the setup wizard's bridge to tools/setup's CLI.

build_call checks a wizard request and builds the fixed CLI arguments, SetupRunner runs
them one at a time with live output, and open_terminal starts a terminal for steps that
need one. Nothing here imports the setup tool; it runs it as a program.
"""

from signal_console.setup_cli.requests import SetupCall, SetupRequestError, build_call
from signal_console.setup_cli.runner import SetupBusy, SetupRunner, default_prefix
from signal_console.setup_cli.terminal import open_terminal, terminal_command

__all__ = [
    "SetupBusy",
    "SetupCall",
    "SetupRequestError",
    "SetupRunner",
    "build_call",
    "default_prefix",
    "open_terminal",
    "terminal_command",
]
