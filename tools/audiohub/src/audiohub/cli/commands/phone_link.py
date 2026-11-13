"""`audiohub phone-link`: print the token link for the phone page of a running `run --phone`.

The link holds this run's secret token, read from the owner-only token file
the phone server writes on start. Open the Tailscale HTTPS link on the phone
(see tools/audiohub/PHONE.md).
"""

import argparse
import sys

from audiohub.cli.command import Command
from audiohub.config import Settings
from audiohub.kernel import read_token

EXIT_OK = 0
EXIT_NOT_RUNNING = 1


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """`phone-link` takes no options of its own."""


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Print the links, or explain that no phone hub is running.

    Returns:
        0 with the links printed, 1 if no `audiohub run --phone` is running.
    """
    # Loaded here, not at module level: every `audiohub` command imports this
    # module through the registry, and phone_mode pulls in the voice stack.
    from audiohub.cli.phone_mode import print_phone_links
    from audiohub.phone import DEFAULT_TOKEN_PATH

    try:
        token = read_token(DEFAULT_TOKEN_PATH)
    except FileNotFoundError:
        print(
            "audiohub: error: no phone hub is running; start `audiohub run --phone` first",
            file=sys.stderr,
        )
        return EXIT_NOT_RUNNING
    print_phone_links(settings, token)
    return EXIT_OK


COMMAND = Command(
    name="phone-link",
    help="print the token link for the phone page of a running `run --phone`",
    add_arguments=add_arguments,
    run=run,
)
