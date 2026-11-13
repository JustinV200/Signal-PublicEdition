# audiohub.loop.hearing

The front half of the voice loop: frames in, transcripts out.

```
FrameSource -> UtteranceSegmenter -> Transcriber (executor) -> Heard
```

## Public API

- `FrameSource`: protocol for an async context manager with `frames()` and a `paused` flag. `audiohub.audio.Microphone` and the phone bridge's `audiohub.phone.RemoteFrameSource` satisfy it.
- `WavFrameSource(path, *, is_realtime=True)`: streams a WAV file as mic frames, paced in real time, then silence until closed. Used by `--input-wav` and tests. `duration_s` gives the file's length.
- `read_wav_mono(path, target_rate=16000)`: an 8/16/32-bit PCM WAV file as float32 mono.
- `Hearing(source, segmenter, transcriber)`
  - Async context manager that opens and closes the source.
  - `await load()` warms Whisper up in an executor.
  - `async for heard in utterances()` yields `Heard(text, started_at, audio_s, stt_s)` and skips empty transcripts.
  - `pause()` / `resume()` give half-duplex while Claude speaks (only with `audio.barge_in` off). Resume resets the segmenter. With barge-in on, nothing pauses: utterances heard over Claude are transcribed and the conversation routes them.
  - `await wait_until_quiet(timeout_s)` waits for a gap in the user's speech.
  - Also `device_in_use`, `model_in_use` and `is_paused`.

## Dependencies

`audiohub.stt` (segmenter, transcriber, frame constants), `audiohub.audio` (`resample`) and `numpy`.
