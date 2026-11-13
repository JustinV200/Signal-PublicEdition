"""Tests for `audiohub say` and `audiohub voices` exit codes and what they speak (no audio)."""

import pytest

import audiohub.loop as loop_api
from audiohub.cli import main
from audiohub.config import loader
from audiohub.tts import BRITISH_MALE_VOICES


class RecordingVoice:
    """Stands in for VoiceOutput; `result` is what speak() reports."""

    def __init__(self, result: bool = True, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, str | None]] = []
        self.result, self.error = result, error

    async def speak(self, text: str, voice: str | None = None) -> bool:
        self.calls.append((text, voice))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture(autouse=True)
def no_local_config(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")


def _use(monkeypatch, voice: RecordingVoice) -> RecordingVoice:
    # The commands import create_voice_output from audiohub.loop when they run.
    monkeypatch.setattr(loop_api, "create_voice_output", lambda settings: voice)
    return voice


def test_say_speaks_with_the_chosen_voice(monkeypatch):
    voice = _use(monkeypatch, RecordingVoice())
    assert main(["say", "Testing, testing.", "--voice", "bm_fable"]) == 0
    assert voice.calls == [("Testing, testing.", "bm_fable")]


@pytest.mark.parametrize(
    ("argv", "voice", "exit_code", "message"),
    [
        (["say", "  "], RecordingVoice(), 2, "nothing to say"),
        (["say", "Hi", "--voice", "x"], RecordingVoice(error=ValueError("Voice x not found")),
         2, "Voice x not found"),
        (["say", "Hi"], RecordingVoice(result=False), 1, ""),
    ],
)  # fmt: skip
def test_say_failures(monkeypatch, capsys, argv, voice, exit_code, message):
    _use(monkeypatch, voice)
    assert main(argv) == exit_code
    assert message in capsys.readouterr().err


def test_voices_announces_each_british_voice_by_name(monkeypatch):
    voice = _use(monkeypatch, RecordingVoice())
    assert main(["voices"]) == 0
    assert [name for _, name in voice.calls] == list(BRITISH_MALE_VOICES)
    assert voice.calls[0][0].startswith("This is George.")
