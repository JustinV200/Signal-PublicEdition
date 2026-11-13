# audiohub.stt

Speech-to-text for the voice loop. 16 kHz microphone frames go in; utterance transcripts come out.

```
frame (512 x float32) -> VoiceActivityDetector -> UtteranceSegmenter -> utterance -> Transcriber -> text
```

## Public API (`from audiohub.stt import ...`)

| Name | What it does |
|---|---|
| `SAMPLE_RATE`, `FRAME_SAMPLES` | 16000 and 512: the frame format everything here expects. |
| `VoiceActivityDetector(threshold)` | `speech_probability(frame) -> float`, `threshold`, `reset()`. Silero VAD (`pysilero-vad`, ggml, CPU). A slow auto-gain (`level.py`, max +20 dB) lifts quiet Bluetooth-mic input before scoring. |
| `UtteranceSegmenter(vad, vad_settings)` | `push(frame) -> np.ndarray \| None` returns a finished utterance (pre-roll + speech + up to a pre-roll of trailing silence). It drops bursts shorter than `min_speech_ms` and force-ends at `max_utterance_s`. Also `reset()` and `is_speaking`. Once speech starts, frames still count as speech down to `max(threshold - 0.15, 0.01)` (hysteresis, as in Silero's reference). |
| `SpeechScorer` | Protocol for the segmenter's VAD, so tests can pass a fake. |
| `Transcriber(stt_settings)` | `transcribe(audio) -> str` (synchronous; use an executor), `load()` to warm up early, plus `device_in_use` and `model_in_use`. Tries the configured model on CUDA, then `fallback_model` on CPU int8. Known Whisper hallucinations are filtered out. |

## Internals

- `frames.py`: frame constants and the shape check.
- `level.py`: `LevelNormalizer`, the auto-gain applied before VAD.
- `vad.py`, `segmenter.py`, `transcriber.py`: the public classes.
- `model_loader.py`: tries each model choice and warms it up with a silent decode. A CUDA model builds fine without cuBLAS and only fails on its first decode, so the warm-up is what makes the CPU fallback reliable.
- `cuda_dlls.py`: on Windows, registers `site-packages/nvidia/*/bin` with `os.add_dll_directory` **and** prepends it to `PATH`. Tested with CTranslate2 4.8.3: `add_dll_directory` alone still fails with "cublas64_12.dll is not found", because CTranslate2 loads cuBLAS with a plain `LoadLibrary`, which searches PATH.
- `hallucinations.py`: removes YouTube-outro sentences ("Thanks for watching!") anywhere in a transcript. It empties transcripts made only of fillers ("Thank you.", "you") and strips sound tags like `[Music]`.

## Dependencies

`audiohub.config` (`SttSettings`, `VadSettings`), `numpy`, `pysilero-vad`, `faster-whisper` (imported lazily on first model load), `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` (Windows CUDA). It never imports `audiohub.audio`.

Measured on a high-end desktop GPU, with a 3.5 s utterance: `large-v3-turbo` on CUDA float16 loads and warms up in 2.2 s and transcribes in about 70 ms. The CPU fallback (`small.en` int8) takes about 0.9 s.

Whisper models download into the Hugging Face cache (`~/.cache/huggingface/hub`) on first load: about 1.6 GB for `large-v3-turbo`.
