"""Registry of `vault` subcommands. Each module defines NAME, HELP, add_arguments() and run()."""

from types import ModuleType

from vault.cli.commands import add_cmd, init_cmd, list_cmd, policy_cmd, remove_cmd

COMMANDS: tuple[ModuleType, ...] = (init_cmd, add_cmd, list_cmd, remove_cmd, policy_cmd)

__all__ = ["COMMANDS"]
