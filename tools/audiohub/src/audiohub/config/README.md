# audiohub.config

Settings for every other audiohub package: frozen dataclasses with defaults in code, an optional TOML override file, and the tool's well-known paths.

## Public API (`from audiohub.config import ...`)

- `load_settings(path: Path | None = None) -> Settings`
  - With `None`, reads `DEFAULT_CONFIG_PATH` if it exists, otherwise returns defaults.
  - An explicit path must exist.
  - Raises `ConfigError` (a `ValueError`) on unreadable or invalid TOML, unknown sections or keys, wrong types, and out-of-range numbers. The message names the file and the `section.key`.
- `Settings` has one frozen section per TOML table: `audio`, `ducking`, `stt`, `vad`, `tts`, `brain`, `kernel`, `wake`, `ipc`, `phone`, `music`. The section classes (`AudioSettings`, `DuckingSettings`, ...) are exported too.
  - `music.backend` must be one of `MUSIC_BACKENDS` (`auto`, `spotify`, `smtc`).
  - List settings are tuples.
  - An int is accepted where a float is expected. NaN and infinity are rejected.
  - `brain.model` must be one of signal_modelchoice's `MODEL_ALIASES` (default `sonnet`) and `brain.effort` one of `EFFORT_LEVELS` (default `low`). Both are always passed to the CLI.
  - Change a value with `dataclasses.replace`.
- `with_brain_choice(settings.brain, BRAIN_CHOICE_PATH)`: the brain settings with the console's voice pick applied; an unset or unlisted value keeps the TOML one.
- Paths:
  - `TOOL_ROOT` is `tools/audiohub`
  - `REPO_ROOT` is the monorepo root
  - `MODELS_DIR` is `tools/audiohub/models` (gitignored)
  - `CACHE_DIR` is `tools/audiohub/.cache` (gitignored), for small runtime state that must survive a crash
  - `BRAIN_CHOICE_PATH` is `tools/audiohub/.cache/brain-choice.json`, voice's model and effort pick, which the console writes and the brain reads before each turn
  - `DEFAULT_CONFIG_PATH` is `tools/audiohub/audiohub.toml` (gitignored)
  - `ORCHESTRATOR_CLAIM_PATH` is `tools/console/.state/orchestrator.json`, the orchestrator claim `console claim` writes; the voice hand-off reads it

Every key, with its default, is documented in `tools/audiohub/audiohub.example.toml`.

## Files

- `paths.py`: path constants. They assume uv's editable install.
- `settings.py`: section dataclasses and defaults.
- `validation.py`: `ConfigError`, the `bounded()` and `one_of()` field helpers, and per-section type/range/choice checks.
- `loader.py`: reads TOML and builds `Settings`.

## Dependencies

Standard library only (`tomllib`, `dataclasses`, `typing`). Imports nothing else from audiohub.
