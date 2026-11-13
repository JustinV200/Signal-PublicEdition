"""`audiohub run [--no-listen] [--input-wav FILE] [--phone]`: the hub, until Ctrl+C.

Full mode is the voice loop: glasses mic -> Whisper -> Claude -> kernel ->
TTS, with the notification server alongside. `--no-listen` runs a
speak-only hub (kernel, notifications and voice output; no mic or Claude
session). `--input-wav` feeds a file in instead of the mic. `--phone` hears
and speaks through the phone page instead of local devices (phone_mode.py).
"""

import argparse
import asyncio
import sys

from audiohub.cli.command import Command
from audiohub.cli.commands.listen import add_input_wav_option
from audiohub.config import Settings

EXIT_OK = 0
EXIT_USER_ERROR = 2


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the `run` options."""
    parser.add_argument(
        "--no-listen",
        dest="listen",
        action="store_false",
        help="speak-only hub: kernel, notifications and voice output, no mic or Claude session",
    )
    add_input_wav_option(parser)
    parser.add_argument(
        "--phone",
        action="store_true",
        help="hear and speak through the phone page (over Tailscale) instead of local "
        "devices; see tools/audiohub/PHONE.md",
    )


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Run the hub until Ctrl+C (which main turns into exit code 130).

    Returns:
        0 if the hub stops by itself, 2 for conflicting options or a taken
        notification or phone port.
    """
    # The voice stack loads here, not at module level: every `audiohub`
    # command imports this module through the registry.
    from audiohub.cli.phone_mode import run_phone_hub
    from audiohub.loop import Conversation, HubIo, HubStartError, build_parts

    conflict = _option_conflict(args)
    if conflict:
        print(f"audiohub: error: {conflict}", file=sys.stderr)
        return EXIT_USER_ERROR
    if args.phone:
        hub = run_phone_hub(settings)
    else:
        parts = build_parts(settings, args.listen, HubIo(source=args.input_wav))
        hub = Conversation(settings, args.listen, parts).run()
    try:
        asyncio.run(hub)
    except HubStartError as error:
        print(f"audiohub: error: {error}", file=sys.stderr)
        return EXIT_USER_ERROR
    return EXIT_OK


def _option_conflict(args: argparse.Namespace) -> str | None:
    """Explain why the options can't be combined, or None if they can."""
    if args.input_wav is not None and not args.listen:
        return "--input-wav needs listening; drop --no-listen"
    if args.phone and (args.input_wav is not None or not args.listen):
        return "--phone listens and speaks through the phone; drop --input-wav and --no-listen"
    return None


COMMAND = Command(
    name="run",
    help="run the hub: the full voice loop, or speak-only with --no-listen",
    add_arguments=add_arguments,
    run=run,
)
