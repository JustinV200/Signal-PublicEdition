"""`audiohub say TEXT [--voice V]`: speak text straight through TTS, bypassing the kernel.

The quickest end-to-end check of the output path: Kokoro, the output device
and music ducking.
"""

import argparse
import asyncio
import sys

from audiohub.cli.command import Command
from audiohub.config import Settings

EXIT_OK = 0
EXIT_PLAYBACK_FAILED = 1
EXIT_USER_ERROR = 2


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the `say` arguments."""
    parser.add_argument("text", metavar="TEXT", help="what to say")
    parser.add_argument(
        "--voice",
        metavar="V",
        help="Kokoro voice (default: the configured one; `audiohub voices` plays the "
        "British male ones)",
    )


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Speak the text and wait until it has played.

    Returns:
        0 when played, 1 if the output device failed, 2 for blank text or an
        unknown voice.
    """
    if not args.text.strip():
        print("audiohub: error: nothing to say", file=sys.stderr)
        return EXIT_USER_ERROR
    # The voice stack loads here, not at module level: every `audiohub`
    # command imports this module through the registry.
    from audiohub.loop import create_voice_output

    voice_output = create_voice_output(settings)
    try:
        is_played = asyncio.run(voice_output.speak(args.text, voice=args.voice))
    except ValueError as error:
        # Kokoro raises ValueError for a voice that isn't in its voices file.
        print(f"audiohub: error: {error}", file=sys.stderr)
        return EXIT_USER_ERROR
    return EXIT_OK if is_played else EXIT_PLAYBACK_FAILED


COMMAND = Command(
    name="say",
    help="speak TEXT through text-to-speech (bypasses the kernel)",
    add_arguments=add_arguments,
    run=run,
)
