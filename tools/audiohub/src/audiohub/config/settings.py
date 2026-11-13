"""Frozen settings dataclasses: one per config section, plus the `Settings` root.

All defaults live here. A TOML file (see loader.py and audiohub.example.toml)
overrides them key by key. List-valued settings are tuples so the dataclasses
stay truly immutable. Fields declared with `bounded()` get range-checked on load,
and fields declared with `one_of()` are checked against their allowed values.
"""

from dataclasses import dataclass, field

from signal_modelchoice import EFFORT_LEVELS, MODEL_ALIASES

from audiohub.config.paths import BRIEF_AWAY_PATH, SLEEPMODE_STATE_PATH
from audiohub.config.validation import bounded, one_of

# Values accepted by [music] backend. "auto" = Spotify Web API, falling back to
# the Windows media session for play/pause/skip when Spotify can't be used.
MUSIC_BACKENDS: tuple[str, ...] = ("auto", "spotify", "smtc")


@dataclass(frozen=True)
class AudioSettings:
    """Which sound devices to use: a name substring, a device index, or None for the default.

    `barge_in` keeps the mic live while Claude speaks, so the user can cut in
    with "stop" or "Hey Claude, ..."; False mutes it then (half-duplex).
    `echo_tail_s` is how long after Claude stops speaking its voice may still
    reach the mic, since Bluetooth output lags about 1.7 s. The mic stays
    muted for that long (half-duplex), or what it hears is still checked
    against Claude's words (barge-in). With barge-in, an utterance begun
    `reply_after_s` or more after Claude's audio ended (capped at
    `echo_tail_s`), once the user heard it stop, is a reply; one begun
    earlier still counts as talking over Claude. `wake_chime` plays a short
    chime when a wake phrase is accepted, at `wake_chime_volume` (peak, 0-1).
    """

    input_device: str | int | None = None
    output_device: str | int | None = None
    barge_in: bool = True
    echo_tail_s: float = bounded(2.0, minimum=0.0, maximum=10.0)
    reply_after_s: float = bounded(1.3, minimum=0.0, maximum=10.0)
    wake_chime: bool = True
    wake_chime_volume: float = bounded(0.45, minimum=0.0, maximum=1.0)


@dataclass(frozen=True)
class DuckingSettings:
    """Turning music down while Claude speaks.

    `level` is the fraction of each process's current session volume to fade to.
    """

    enabled: bool = True
    processes: tuple[str, ...] = ("Spotify.exe",)
    level: float = bounded(0.15, minimum=0.0, maximum=1.0)
    fade_ms: int = bounded(250, minimum=0)


@dataclass(frozen=True)
class SttSettings:
    """Whisper speech-to-text model choice, with a CPU fallback model."""

    model: str = "large-v3-turbo"
    device: str = "cuda"
    compute_type: str = "float16"
    fallback_model: str = "small.en"
    language: str = "en"


@dataclass(frozen=True)
class VadSettings:
    """Voice-activity detection and utterance segmentation thresholds."""

    threshold: float = bounded(0.5, minimum=0.0, maximum=1.0)
    min_silence_ms: int = bounded(700, minimum=0)
    min_speech_ms: int = bounded(250, minimum=0)
    pre_roll_ms: int = bounded(300, minimum=0)
    max_utterance_s: float = bounded(30.0, minimum=1.0)


@dataclass(frozen=True)
class TtsSettings:
    """Kokoro text-to-speech voice. kokoro-onnx accepts speeds from 0.5 to 2.0."""

    voice: str = "bm_george"
    speed: float = bounded(1.0, minimum=0.5, maximum=2.0)
    lang: str = "en-gb"


@dataclass(frozen=True)
class BrainSettings:
    """The Claude Code session the user talks to.

    `model` and `effort` are always passed to the CLI explicitly. Voice loads
    the repo's local settings, so leaving them unset would hand it whatever
    model and effort the console last picked for new orchestrator sessions.
    The console's voice pick (brain-choice.json) overrides both per turn.

    `turn_stall_timeout_s` is how long a turn may show no activity at all (no
    text, tool call or tool result) before the brain gives up on it, so a lost
    result can't wedge the voice loop.
    """

    model: str = one_of("sonnet", MODEL_ALIASES)
    effort: str = one_of("low", EFFORT_LEVELS)
    # Voice is a thin, fast layer (music, whiteboard, brief, quick lookups); any
    # other tool call is refused quietly and handed to the main Signal session
    # (see brain/permissions/gate.py). These run without a question: exact tool
    # names, then MCP servers (by exact name) whose every tool may run.
    auto_allow_tools: tuple[str, ...] = (
        "Read",
        "Glob",
        "Grep",
        "WebSearch",
        "mcp__mail__mail_accounts",
        "mcp__mail__mail_search",
        "mcp__mail__mail_read",
        "mcp__mail__mail_thread",
        "mcp__sessions__list_sessions",
        "mcp__sessions__list_managed_sessions",
        "mcp__sessions__list_repos",
        "mcp__sessions__session_status",
        # The brief, minus brief_log and brief_undo: text voice reads (mail, the
        # web) mustn't log a trusted brief entry or undo one.
        "mcp__brief__brief_me",
        "mcp__brief__brief_get",
        "mcp__brief__brief_ack",
        "mcp__brief__brief_resolve",
        "mcp__brief__away_on",
        "mcp__brief__away_off",
        "mcp__brief__away_status",
    )
    auto_allow_mcp_servers: tuple[str, ...] = ("audiohub", "whiteboard", "sleepmode")
    turn_stall_timeout_s: float = bounded(300.0, minimum=1.0)


@dataclass(frozen=True)
class KernelSettings:
    """The Sonnet dispatcher that orders and condenses every user-bound message."""

    model: str = "sonnet"
    max_spoken_words: int = bounded(80, minimum=1)
    hold_recheck_s: float = bounded(30.0, minimum=0.0)
    decision_timeout_s: float = bounded(8.0, minimum=0.0)


@dataclass(frozen=True)
class WakeSettings:
    """Wake phrases, and how long after Claude speaks a reply needs no wake phrase."""

    phrases: tuple[str, ...] = ("hey claude", "claude", "hey signal")
    require_wake: bool = True
    follow_up_s: float = bounded(8.0, minimum=0.0)


@dataclass(frozen=True)
class IpcSettings:
    """Where the hub's kernel TCP server listens for notifications, and when it drops them.

    Notifications are dropped unspoken while sleepmode's `sleep_state_file`
    says the owner is asleep or the brief's `away_state_file` says the owner is away.
    """

    host: str = "127.0.0.1"
    port: int = bounded(8765, minimum=1, maximum=65535)
    sleep_state_file: str = str(SLEEPMODE_STATE_PATH)
    away_state_file: str = str(BRIEF_AWAY_PATH)


@dataclass(frozen=True)
class PhoneSettings:
    """The phone bridge (`audiohub run --phone`): the phone page's port and who may load it.

    The server always binds 127.0.0.1; Tailscale Serve proxies the phone to it.
    `allowed_hosts` are the extra Host/Origin names accepted besides localhost,
    normally this PC's MagicDNS name (e.g. "pc.tail1234.ts.net"). `echo_tail_s`
    replaces `audio.echo_tail_s` in phone mode, since the phone's network and
    Bluetooth output lag more than the PC's, and `audio.reply_after_s` moves
    by the difference.
    """

    port: int = bounded(8781, minimum=1, maximum=65535)
    allowed_hosts: tuple[str, ...] = ()
    echo_tail_s: float = bounded(2.5, minimum=0.0, maximum=10.0)


@dataclass(frozen=True)
class MusicSettings:
    """Music control backend, the Spotify OAuth redirect URI, and pausing music for Claude.

    Spotify rejects `localhost` redirect URIs, so the default is a loopback IP.
    It must match the redirect URI registered on the Spotify developer app.
    `pause_on_wake` makes the hub pause playing music when it hears its wake
    phrase, keep it paused through the conversation, and pause it around any
    other speech too (a notification). It resumes `resume_after_s` after the
    conversation ends, and only if the same track is still paused and Claude
    wasn't asked to play or pause; after Claude skips a track, whatever is
    paused is resumed.
    """

    backend: str = one_of("auto", MUSIC_BACKENDS)
    redirect_uri: str = "http://127.0.0.1:8888/callback"
    pause_on_wake: bool = True
    resume_after_s: float = bounded(2.0, minimum=0.0, maximum=60.0)


@dataclass(frozen=True)
class Settings:
    """All audiohub settings. Each attribute is one [section] of the TOML file."""

    audio: AudioSettings = field(default_factory=AudioSettings)
    ducking: DuckingSettings = field(default_factory=DuckingSettings)
    stt: SttSettings = field(default_factory=SttSettings)
    vad: VadSettings = field(default_factory=VadSettings)
    tts: TtsSettings = field(default_factory=TtsSettings)
    brain: BrainSettings = field(default_factory=BrainSettings)
    kernel: KernelSettings = field(default_factory=KernelSettings)
    wake: WakeSettings = field(default_factory=WakeSettings)
    ipc: IpcSettings = field(default_factory=IpcSettings)
    phone: PhoneSettings = field(default_factory=PhoneSettings)
    music: MusicSettings = field(default_factory=MusicSettings)
