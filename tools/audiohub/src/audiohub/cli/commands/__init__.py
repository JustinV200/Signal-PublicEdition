"""Registry of `audiohub` subcommands, one module per command.

Add a command by creating a module here that defines `COMMAND` and listing it
below. `audiohub --help` shows commands in this order.
"""

from audiohub.cli import hub_check
from audiohub.cli.command import Command
from audiohub.cli.commands import (
    devices,
    listen,
    mcp,
    music,
    notify,
    phone_link,
    run,
    say,
    voices,
)

COMMANDS: tuple[Command, ...] = (
    devices.COMMAND,
    say.COMMAND,
    voices.COMMAND,
    listen.COMMAND,
    run.COMMAND,
    phone_link.COMMAND,
    notify.COMMAND,
    mcp.COMMAND,
    music.COMMAND,
    hub_check.COMMAND,
)

__all__ = ["COMMANDS"]
