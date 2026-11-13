"""`audiohub voices`: speak a sample in each British male voice, so the owner can pick one.

Each voice announces its own name first ("This is George."), and the console
shows which config value selects it.
"""

import argparse
import asyncio
from typing import TYPE_CHECKING

from audiohub.cli.command import Command
from audiohub.config import Settings

if TYPE_CHECKING:
    from audiohub.loop import VoiceOutput

EXIT_OK = 0
EXIT_PLAYBACK_FAILED = 1

SAMPLE_LINE = (
    "Good afternoon. Your build passed, the kettle's on, and there's one new message waiting."
)
# Kokoro names voices "<accent+gender>_<name>", e.g. "bm_george".
_VOICE_NAME_SEPARATOR = "_"


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """`voices` takes no options of its own."""


def run(args: argparse.Namespace, settings: Settings) -> int:
    """Play every British male voice in turn.

    Returns:
        0 when all played, 1 if the output device failed on any of them.
    """
    # The voice stack loads here, not at module level: every `audiohub`
    # command imports this module through the registry.
    from audiohub.loop import create_voice_output

    return asyncio.run(_play_samples(create_voice_output(settings)))


def spoken_name(voice: str) -> str:
    """Turn a Kokoro voice id into the name it announces: "bm_george" -> "George"."""
    return voice.split(_VOICE_NAME_SEPARATOR, 1)[-1].capitalize()


async def _play_samples(voice_output: "VoiceOutput") -> int:
    from audiohub.tts import BRITISH_MALE_VOICES

    is_all_played = True
    for voice in BRITISH_MALE_VOICES:
        print(f'{voice}  (tts.voice = "{voice}")', flush=True)
        text = f"This is {spoken_name(voice)}. {SAMPLE_LINE}"
        is_all_played &= await voice_output.speak(text, voice=voice)
    return EXIT_OK if is_all_played else EXIT_PLAYBACK_FAILED


COMMAND = Command(
    name="voices",
    help="speak a sample in each British male voice, announcing its name",
    add_arguments=add_arguments,
    run=run,
)
