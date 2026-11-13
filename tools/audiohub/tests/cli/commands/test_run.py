"""Tests for `audiohub run` and `audiohub listen` option handling (nothing real is started)."""

import wave

import pytest

import audiohub.loop as loop_api
from audiohub.cli import main
from audiohub.config import loader
from audiohub.loop import HubStartError


class RecordingConversation:
    """Stands in for Conversation and records how it was built."""

    instances: list["RecordingConversation"] = []
    error: Exception | None = None

    def __init__(self, settings, listen, parts) -> None:
        self.listen, self.parts = listen, parts
        RecordingConversation.instances.append(self)

    async def run(self) -> None:
        if RecordingConversation.error is not None:
            raise RecordingConversation.error


@pytest.fixture(autouse=True)
def fake_hub(tmp_path, monkeypatch):
    monkeypatch.setattr(loader, "DEFAULT_CONFIG_PATH", tmp_path / "absent.toml")
    RecordingConversation.instances, RecordingConversation.error = [], None
    built = []
    # `run` imports these from audiohub.loop when it runs.
    monkeypatch.setattr(loop_api, "Conversation", RecordingConversation)
    monkeypatch.setattr(
        loop_api, "build_parts", lambda *args, **kwargs: built.append((args, kwargs))
    )
    return built


def test_no_listen_runs_a_speak_only_hub(fake_hub):
    assert main(["run", "--no-listen"]) == 0
    ((args, kwargs),) = fake_hub
    assert args[1] is False and args[2].source is None
    assert RecordingConversation.instances[0].listen is False


def test_input_wav_is_rejected_without_listening(tmp_path, capsys):
    wav = tmp_path / "silence.wav"
    _write_silent_wav(wav)
    assert main(["run", "--no-listen", "--input-wav", str(wav)]) == 2
    assert "--input-wav needs listening" in capsys.readouterr().err


def test_taken_port_is_a_clean_error(capsys):
    RecordingConversation.error = HubStartError("is another audiohub already running?")
    assert main(["run"]) == 2
    assert "another audiohub" in capsys.readouterr().err


def test_unreadable_input_wav_is_a_usage_error(tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["listen", "--input-wav", str(tmp_path / "missing.wav")])
    assert exit_info.value.code == 2
    assert "--input-wav" in capsys.readouterr().err


def _write_silent_wav(path) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * 1600)
