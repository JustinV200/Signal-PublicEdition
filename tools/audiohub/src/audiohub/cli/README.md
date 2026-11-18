# audiohub.cli

The `audiohub` command line. `pyproject.toml` maps the script to `audiohub.cli.main:main`, and `python -m audiohub` does the same.

## Public API

- `main(argv=None) -> int`: parses arguments, loads settings, runs the command, and returns the exit code.
  - Config errors, unknown devices and devices that won't open print `audiohub: error: ...` and exit 2.
  - Ctrl+C exits 130.

## Global options

Accepted before or after the command name:
- `--config PATH`: the settings file. Defaults to `tools/audiohub/audiohub.toml` if it exists.
- `--input-device DEVICE` / `--output-device DEVICE`: a name substring, or an index (all digits). These override `[audio]` in the config.

## Commands

Commands that run until stopped exit 130 on Ctrl+C.

- `devices [--all]`
  - Lists WASAPI and MME devices. `--all` adds DirectSound and WDM-KS.
  - Marks the default input/output and likely `hands-free` and `bluetooth` endpoints.
  - Shows what the configured devices resolve to. Exits 1 if one doesn't resolve.
- `say TEXT [--voice V]`
  - Speaks text through Kokoro with music ducked, bypassing the kernel.
  - Exits 1 if the output device failed, 2 for blank text or an unknown voice.
- `voices`: speaks a sample in each British male voice, announcing its name and printing its `tts.voice` value. Exits 1 if any playback failed.
- `listen [--input-wav FILE]`: prints each utterance with its length and STT latency until Ctrl+C. `--input-wav` feeds a WAV file in instead of the mic.
- `run [--no-listen] [--input-wav FILE] [--phone]`
  - The hub until Ctrl+C: mic, Whisper, Claude, kernel and TTS, with the notification server alongside.
  - `--no-listen` is speak-only: kernel, notifications and voice output, no mic or Claude session.
  - `--phone` hears and speaks through the phone page instead of local devices (`phone_mode.py`, `tools/audiohub/PHONE.md`). It starts the phone page server, prints the token links, and uses `[phone] echo_tail_s`. The brain, kernel, notifications and ducking are unchanged.
  - Exits 2 if `--input-wav` is combined with `--no-listen`, `--phone` with either of them, or the notification or phone port is taken.
- `phone-link`: prints the token links for the phone page of a running `run --phone`, read from `.cache/phone-token`. Exits 1 if none is running.
- `notify TEXT [--source S] [--priority P]`
  - Sends one message to the running hub, to be spoken when the kernel decides. Prints the message id.
  - `--source` defaults to `cli`. `--priority` is `urgent`, `high`, `normal` (default) or `low`.
  - Exits 1 if it wasn't delivered: hub not running, message refused, or connection failed.
- `mcp`: serves the stdio MCP server (see `../mcp/README.md`) until the client closes stdin. Prints nothing to stdout, which carries the protocol.
- `music ACTION`, where `[music] backend` picks Spotify, SMTC or both:
  - `status`: the backend, the Spotify login state and what's playing.
  - `login`: the one-time Spotify browser login. Needs `SPOTIPY_CLIENT_ID`.
  - `play`, `pause`, `toggle`, `next`, `prev`.
  - `volume N`: Spotify's volume, 0-100.
  - `play-search QUERY [--kind track|album|playlist|artist]`: plays the best match.
  - `queue QUERY`: queues the best track match.
  - Exits 1 if the backend can't do it (the reason goes to stderr), 2 for a bad argument.

## Adding a command

1. Create `commands/<name>.py`. Give it a header comment, then define `add_arguments(parser)`, `run(args, settings) -> int` and `COMMAND = Command(name=..., help=..., add_arguments=..., run=...)`.
2. Import the module in `commands/__init__.py` and append `<name>.COMMAND` to `COMMANDS`.
3. Add `tests/cli/commands/test_<name>.py`.

`run` receives settings with the device flags already applied. The global options are added for you.

## Files

| File | Contents |
|---|---|
| `main.py` | parser construction, dispatch, error exits |
| `command.py` | the `Command` record |
| `options.py` | global options, device-spec parsing, settings from args |
| `phone_mode.py` | `run --phone` wiring and the link printout |
| `hub_check.py` | `audiohub check`: installed, and is the hub running (token file plus a bare port connect) |
| `commands/` | one module per command, plus the `COMMANDS` registry |

## Dependencies

Standard library `argparse`. `audiohub.config`, plus what the commands use: `audiohub.audio`, `audiohub.loop`, `audiohub.tts`, `audiohub.kernel`, `audiohub.music`, `audiohub.phone` and `audiohub.mcp` (imported only when `mcp` runs). The heavy ones (`audiohub.loop`, `audiohub.audio`, `audiohub.phone`, the Sonnet side of `audiohub.kernel` and the Spotify side of `audiohub.music`) load inside a command's `run()` or lazily, because every command imports the whole registry: `python -X importtime -c "import audiohub.cli.main"` should stay under 0.3 s.
