# models

The Models page (`ModelsView`, `Ctrl+7`): a header and a hint over the model strip (`ModelStrip`). The orchestrator row shows `now: opus-5-5 · medium` (the claimed session's model from the session hook and its last Stop's effort; `model unknown` / `effort unknown` while unknown) and the next-session pickers, which write `.claude/settings.local.json` and say `applies to every new Signal session, not this one`. A hint says the running session switches from the model name under the VS Code prompt box. The voice row's pickers write voice's pick and say `applies on your next request`.

Each picker (`PickSelect`) is a native select over the server's fixed list (`models.choices` in `/api/state`); a pick sends its index through `pickModel` (POST `/api/models`), never text. Null options read `use my user settings`. A current value that isn't in the list shows as a disabled placeholder (`audiohub.toml default`, `other: X`), and an unreadable settings file shows `can't read settings`, never `use my user settings`. The pickers are disabled with a reason while saving or when the settings file can't be read; a refused write shows its error under the strip. `modelWords.ts` holds the wording.

Public API: `index.ts`. Depends on `api` and `state`.
