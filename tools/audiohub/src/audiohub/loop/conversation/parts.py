"""`ConversationParts`: everything a Conversation runs, and `build_parts` to make the real set.

Keeping construction here lets tests and hands-off runs swap single parts,
e.g. a WavFrameSource for the microphone, or fakes for the brain and kernel.
`HubIo` swaps the hub's local mic, speaker and console status line, which is
how `audiohub run --phone` hears and speaks through the phone instead.
"""

from dataclasses import dataclass
from pathlib import Path

from audiohub.brain import ClaudeBrain
from audiohub.config import REPO_ROOT, MusicSettings, Settings
from audiohub.kernel import Kernel, KernelServer, PresenceFiles
from audiohub.music import create_controller

from ..factories import create_hearing, create_voice_output
from ..hearing import FrameSource, Hearing
from ..music_pause import MusicPause
from ..status import StatusLine
from ..voice_output import AudioPlayer, VoiceOutput
from .hub_record import HUB_RECORD_PATH
from .turns import VoiceBrain, background_forwarder


@dataclass(frozen=True)
class ConversationParts:
    """The components of one hub. `hearing` and `brain` are None for a speak-only hub.

    Attributes:
        kernel: Decides what is spoken, and when.
        server: Accepts notifications from other processes into the kernel.
        voice: Speaks to the user, ducking music.
        status: The console status line.
        hearing: Mic -> transcripts, or None when not listening.
        brain: The Claude session, or None when not listening.
        music_pause: Pauses the music while the user talks with Claude, or
            None to leave it alone (`music.pause_on_wake` off).
        record_path: Where the hub records its pid for the console's Stop
            (hub_record.py), or None to write no record (tests).
    """

    kernel: Kernel
    server: KernelServer
    voice: VoiceOutput
    status: StatusLine
    hearing: Hearing | None = None
    brain: VoiceBrain | None = None
    music_pause: MusicPause | None = None
    record_path: Path | None = None


@dataclass(frozen=True)
class HubIo:
    """Stand-ins for the hub's local mic, speaker and console status line. None keeps the default.

    Attributes:
        source: Frames to listen to instead of the configured microphone,
            e.g. a WavFrameSource or the phone's RemoteFrameSource.
        speaker: Plays speech instead of the configured output device.
        status: The status line to report to instead of a plain console one.
    """

    source: FrameSource | None = None
    speaker: AudioPlayer | None = None
    status: StatusLine | None = None


def build_parts(
    settings: Settings, listen: bool = True, io: HubIo | None = None
) -> ConversationParts:
    """Build the real hub components from settings.

    Args:
        settings: The loaded settings.
        listen: False builds a speak-only hub: kernel, IPC and voice output.
        io: Replacements for the local mic, speaker or status line.

    Returns:
        Unstarted parts; `Conversation.run` starts and stops them. Audio
        devices are looked up when they open, not here.
    """
    io = io or HubIo()
    status = io.status or StatusLine()
    kernel = Kernel(settings.kernel)
    ipc = settings.ipc
    presence = PresenceFiles(Path(ipc.sleep_state_file), Path(ipc.away_state_file))
    server = KernelServer(kernel, ipc.host, ipc.port, presence=presence)
    voice = create_voice_output(settings, io.speaker)
    music_pause = _build_music_pause(settings.music)
    if not listen:
        return ConversationParts(
            kernel,
            server,
            voice,
            status,
            music_pause=music_pause,
            record_path=HUB_RECORD_PATH,
        )
    brain = ClaudeBrain(
        settings.brain,
        REPO_ROOT,
        on_background_text=background_forwarder(kernel.submit, status),
        on_tool_call=music_pause.note_tool_call if music_pause is not None else None,
    )
    hearing = create_hearing(settings, io.source)
    return ConversationParts(
        kernel, server, voice, status, hearing, brain, music_pause, HUB_RECORD_PATH
    )


def _build_music_pause(music_settings: MusicSettings) -> MusicPause | None:
    """The configured music backend behind a MusicPause, or None with `pause_on_wake` off."""
    if not music_settings.pause_on_wake:
        return None
    # Makes no network or Windows calls yet: those happen on the first pause.
    return MusicPause(create_controller(music_settings), music_settings.resume_after_s)
