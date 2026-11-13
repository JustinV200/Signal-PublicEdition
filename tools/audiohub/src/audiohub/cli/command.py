"""The `Command` record that every `audiohub <name>` subcommand module exports.

To add a command: create `cli/commands/<name>.py` defining
`COMMAND = Command(...)`, then append it to `COMMANDS` in
`cli/commands/__init__.py`. main.py builds the argparse subparser from it.
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from audiohub.config import Settings


@dataclass(frozen=True)
class Command:
    """One subcommand.

    Attributes:
        name: The word typed after `audiohub`, e.g. "devices".
        help: One-line description shown in `audiohub --help`.
        add_arguments: Adds the command's own options to its subparser. The
            global --config/--input-device/--output-device are added for it.
        run: Executes the command with the parsed args and the loaded
            settings (device flags already applied). Returns the exit code.
    """

    name: str
    help: str
    add_arguments: Callable[[argparse.ArgumentParser], None]
    run: Callable[[argparse.Namespace, Settings], int]
