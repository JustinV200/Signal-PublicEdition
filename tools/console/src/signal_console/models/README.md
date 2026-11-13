# models

The model strip's data, and the picks the owner makes there. Every path comes in through `ModelFiles`, so tests use tmp copies and never the real settings.

- `files.py`: `ModelFiles(settings, backup, session_models, brain_choice, lock)`; `ModelFiles.for_repo(state_dir)` gives the real ones.
- `session_models.py`: `.state/session-models.json`, `{session_id: {model, at}}` for the 20 newest sessions. `record_session_model(path, session_id, model, at)` (the session hook; under the jsonstate lock; a report older than the entry on file is ignored) and `read_session_model(path, session_id)`. Only values matching `MODEL_ID_PATTERN` are stored or shown.
- `settings_writer.py`: `write_local_setting(SettingsFiles(settings, backup), key, value)`. Only `model` and `effortLevel`, only to `signal_modelchoice` values or removed (None). Refuses (`SettingsWriteError`) a missing or malformed file, backs it up, then re-reads it and writes only if unchanged (one retry). The file is byte-identical after any refusal.
- `picks.py`: `pick_options(target, field)` (orchestrator lists start with None, "use my user settings") and `apply_pick(files, target, field, index)`, which holds `files.lock` and writes the settings or voice's `brain-choice.json`. `PickError` for a bad target, field or index.
- `snapshot.py`: `models_state(files, session_id, effort, is_claimed=...)`, the `/api/state` `models` block: `orchestrator.now` (claimed session's model and last Stop's effort), `orchestrator.next` (the settings' pick; null if unreadable), `voice` and `choices`.

Public API: `signal_console.models`. Depends on `paths`, `signal_jsonstate` and `signal_modelchoice`; stdlib otherwise, so the session hook loads it cheaply.
