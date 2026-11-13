# signal_modelchoice (packages/modelchoice)

The fixed lists a Signal model or effort pick comes from, and the format of voice's pick file. Shared by the console (which writes picks) and the voice brain (which reads them), so the two can't drift apart. Stdlib only.

## Public API (`from signal_modelchoice import ...`)

- `MODEL_ALIASES`: Claude Code's documented aliases (`default`, `best`, `fable`, `opus`, `sonnet`, `haiku`, `opus[1m]`, `sonnet[1m]`, `opusplan`).
- `EFFORT_LEVELS`: `low`, `medium`, `high`, `xhigh` (`max` isn't accepted in settings files).
- `BrainChoice(model, effort)`: voice's pick; None means unset (audiohub.toml decides). `as_json()` gives the file's object.
- `read_brain_choice(path)`: reads `tools/audiohub/.cache/brain-choice.json`. A value not in the lists is logged and read as None; a missing or malformed file reads as all None. Never raises.

## Depends on

Nothing. Add it with `uv add --editable ../../packages/modelchoice`.

## Tests

`uv run --frozen --no-sync pytest`
