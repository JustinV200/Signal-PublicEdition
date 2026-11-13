"""`audiohub listen [--input-wav FILE]`: live transcription test, until Ctrl+C.

Opens the microphone once, then prints each utterance with its length and
STT latency. Use it to check the glasses mic, VAD thresholds and Whisper
before running the full hub. Also defines the `--input-wav` option that
`run` shares.
"""

import argparse
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from audiohub.cli.command import Command
from audiohub.config import Settings

if TYPE_CHECKING:
    from audiohub.loop import Hearing, StatusLine, WavFrameSource

EXIT_OK = 0


def add_input_wav_option(parser: argparse.ArgumentParser) -> None:
    """Add `--input-wav FILE`: a WAV file played into the pipeline instead of the mic.

    The parsed value is a ready WavFrameSource (or None). A missing or
    unreadable file is reported as a usage error before anything starts.
    """
    parser.add_argument(
        "--input-wav",
        type=_wav_source,
        metavar="FILE",
        help="feed this WAV file in instead of the microphone (testing without the glasses)",
    )


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add the `listen` options."""
    add_input_wav_option(parser)


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Print transcripts until Ctrl+C (which main turns into exit code 130).

    Returns:
        0 if the input ends by itself.
    """
    # The voice stack loads here, not at module level: every `audiohub`
    # command imports this module through the registry.
    from audiohub.loop import StatusLine, create_hearing

    hearing = create_hearing(settings, args.input_wav)
    asyncio.run(_print_transcripts(hearing, StatusLine()))
    return EXIT_OK


async def _print_transcripts(hearing: "Hearing", status: "StatusLine") -> None:
    status.show("loading", "speech model")
    await hearing.load()
    async with hearing:
        status.show("listening", f"stt {hearing.model_in_use} on {hearing.device_in_use}")
        async for heard in hearing.utterances():
            status.show("heard", heard.describe())


def _wav_source(text: str) -> "WavFrameSource":
    from audiohub.loop import WavFrameSource

    try:
        return WavFrameSource(Path(text))
    except (OSError, ValueError) as error:
        raise argparse.ArgumentTypeError(str(error)) from error


COMMAND = Command(
    name="listen",
    help="live transcription test: print each utterance and its STT latency",
    add_arguments=add_arguments,
    run=run,
)
