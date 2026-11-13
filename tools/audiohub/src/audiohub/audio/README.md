# audiohub.audio

Sound I/O for audiohub. It finds devices, streams microphone frames, plays buffers, resamples, and ducks music (lowers other apps' volume) while Claude speaks.

## Public API (`from audiohub.audio import ...`)

### Devices
- `list_devices() -> list[DeviceInfo]`
  - Every PortAudio device, with the host API name, channel counts, native rate, and per-host-API default flags.
  - Names are cleaned up: WDM-KS resource strings become e.g. `Headset (BT-Glasses-01 Hands-Free)`.
- `resolve_device(spec, kind) -> int | None`
  - `None` means the system default.
  - An `int` is a validated index.
  - A `str` is a case-insensitive name substring, searched only under `PREFERRED_HOSTAPIS` (WASAPI first, then MME).
  - Raises `DeviceNotFoundError`.
- `bluetooth_hints(devices) -> dict[int, str]`
  - A name-based guess that maps a device index to `HANDS_FREE` or `BLUETOOTH`.

### Streaming and playback
- `Microphone(device=None, frame_samples=512, target_rate=16000)`
  - Async context manager. `async for frame in mic.frames()` yields float32 mono frames of exactly `frame_samples`.
  - Set `paused = True` to drop audio.
  - The device spec is resolved on `async with`. Raises `DeviceNotFoundError`, or `AudioStreamError` if the device can't be opened or started (a stream that won't start is closed).
- `Speaker(device=None)`
  - `await play(samples, sample_rate)` resolves the device, resamples to its rate, and returns when playback ends.
  - Raises `AudioStreamError` if playback doesn't finish within the buffer's duration plus `PLAYBACK_DEADLINE_MARGIN_S` (5 s).
  - `stop()` cuts playback short.
  - Plays one buffer at a time. Call it from the loop thread.

### Framing
- `FrameChunker(frame_samples)`: `push(block)` re-cuts blocks of any size into frames of exactly `frame_samples`; `clear()` drops a partial frame. Used by `Microphone` and the phone bridge.

### Resampling
- `resample(samples, from_rate, to_rate)`: whole-buffer conversion with soxr.
- `StreamResampler`: block-by-block conversion for live audio.

### Ducking
- `Ducker(ducking_settings)`
  - `duck()` and `restore()` fade the Windows per-app session volume of the target processes (default `Spotify.exe`).
  - `ducked()` wraps both in a context manager.
  - Never raises. Restore puts back the exact captured volume, falls back to a direct set if the fade fails, and runs on errors too.
  - Each call blocks for about `fade_ms`. The two calls share a lock, so a restore never overtakes a duck that's still fading.
  - Captured volumes persist in `tools/audiohub/.cache/ducking.json` until restored, and a crashed run's leftovers are recovered (only while still at the ducked level). See `ducking/README.md`.
- `list_session_process_names()`: diagnostic list of the processes that have audio sessions.

## Notes
- Streams open at the device's reported native rate, in mono float32. WASAPI streams also set `auto_convert`, because a Bluetooth output switches to 16 kHz Hands-Free when its mic opens while PortAudio still reports the old rate.
- Device specs are resolved again on every open. When no audiohub stream is open, PortAudio is refreshed first (about 20 ms), because Bluetooth reconnects renumber devices and PortAudio only lists devices once at start-up.
- The user's glasses: input `Headset (BT-Glasses-01)` (16 kHz) and a single output `Headphones (BT-Glasses-01)` (44.1 kHz stereo, Hands-Free while the mic is open). `"BT-Glasses"` matches both.
- Opening the glasses' mic switches them to the Hands-Free profile. Measured: frames start 1-2 s after the stream opens, and output played during the switch runs up to 1.7 s late. Open the Microphone once and keep it open, not once per utterance.
- Ducker finds sessions on every active render endpoint and keeps no COM objects between calls, so it's safe to call from executor threads.

## Files

| File | Contents |
|---|---|
| `devices.py` | `DeviceInfo`, listing, resolution |
| `device_names.py` | name cleanup, Bluetooth hints |
| `streams.py` | refreshes PortAudio, opens, starts and closes native-rate mono streams |
| `framing.py` | `FrameChunker` |
| `resample.py` | soxr wrappers |
| `microphone.py` | `Microphone` |
| `speaker.py` | `Speaker` |
| `ducking/` | `Ducker` and its pycaw session helpers (own README) |

## Dependencies
- Libraries: `sounddevice`, `numpy`, `soxr`, `pycaw`, `comtypes`, `psutil`.
- Inside audiohub: only `audiohub.config` (`DuckingSettings`).
