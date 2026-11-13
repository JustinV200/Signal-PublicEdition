"""`audiohub notify TEXT`: send one message to a running hub, to be spoken to the user.

A thin wrapper over `audiohub.kernel.send_notification` for scripts and manual
testing. The hub's kernel decides when the message is spoken. Prints the
message id on success; exits 1 with a one-line error if it wasn't delivered.
"""

import argparse
import sys

from audiohub.cli.command import Command
from audiohub.config import Settings
from audiohub.kernel import (
    PRIORITIES,
    HubNotRunningError,
    NotificationRejectedError,
    ProtocolError,
    send_notification,
)

EXIT_OK = 0
EXIT_NOT_DELIVERED = 1
DEFAULT_SOURCE = "cli"
DEFAULT_PRIORITY = "normal"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the `notify` arguments: the text plus --source and --priority."""
    parser.add_argument("text", metavar="TEXT", help="what the user should hear")
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"who the message is from (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--priority",
        choices=PRIORITIES,
        default=DEFAULT_PRIORITY,
        help=f"how important it is (default: {DEFAULT_PRIORITY})",
    )


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Send the notification to the hub at `settings.ipc`.

    Returns:
        0 once the hub has queued it, 1 if it wasn't delivered (hub not
        running, message refused, or the connection failed).
    """
    ipc = settings.ipc
    try:
        message_id = send_notification(ipc.host, ipc.port, args.source, args.text, args.priority)
    except (HubNotRunningError, NotificationRejectedError, ProtocolError, OSError) as error:
        # OSError covers a reply timeout and a dropped connection.
        detail = str(error) or type(error).__name__
        print(f"audiohub: error: message not delivered: {detail}", file=sys.stderr)
        return EXIT_NOT_DELIVERED
    print(f"Sent to the hub as message {message_id}.")
    return EXIT_OK


COMMAND = Command(
    name="notify",
    help="send a message to the running hub, to be spoken to the user",
    add_arguments=add_arguments,
    run=run,
)
