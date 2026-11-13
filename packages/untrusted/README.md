# signal_untrusted (packages/untrusted)

The frame Signal tools put outside text in (plan lines, mail, brief entries) before a model reads it. A fixed trusted line says what the data is, then the data follows as JSON inside one `<untrusted_..._content>` tag pair, with every `<` escaped so the text can't close the frame or open a look-alike tag.

Generalised from the whiteboard's `plan_data` helper (`tools/whiteboard/src/whiteboard/todo/plan_frame.py`). The whiteboard should switch to this package once its TODO-view round is committed: `plan_data(data)` is `framed(PLAN_DATA_NOTE, data, "untrusted_plan_content")`.

## Public API (`from signal_untrusted import ...`)

- `safe_json(data) -> str`: one line of JSON with every `<` escaped (and, as json.dumps does, every non-ASCII and control character), for data that must sit outside a frame, like the brief's undo action.
- `frame(data, tag) -> str`: `<tag>JSON</tag>` on one line. Raises `ValueError` for a tag not matching `TAG_PATTERN` (`untrusted_<name>_content`).
- `framed(trusted_line, data, tag) -> str`: the trusted line, a newline, then the frame. Raises `ValueError` if the trusted line has a line break.

## Depends on

The standard library only (json). Add it with `uv add --editable ../../packages/untrusted`.

## Tests

`uv run --frozen --no-sync pytest`
