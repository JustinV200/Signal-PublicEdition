# signal_jsonstate (packages/jsonstate)

A state folder's cross-process lock and its atomic JSON files. Extracted from `signal_brief.store` so the brief and the console's tasks (`packages/tasks`) share one writer instead of each keeping a copy. Windows only (`msvcrt`).

## Public API (`from signal_jsonstate import ...`)

- `state_lock(lock_path)`: context manager holding a byte-range lock on `lock_path` (created if missing), waiting up to 2 s. The OS drops it when the process dies. Not re-entrant. Raises `StateFileError`.
- `read_json_object(path)`: the object in `path`, or `{}` for a missing or malformed file (tolerant: a hand edit can't wedge a reader). Raises `StateFileError` when the file exists but can't be read.
- `read_bytes_retrying(path)`: the bytes, retried briefly while Windows has the file mid-replace.
- `write_json_atomic(path, payload)` (`indent=1`), `write_text_atomic(path, text)`: create the folder if missing, write a temp file, then `os.replace`, retried while a reader holds the file. Raises `StateFileError`.
- `StateFileError`: any read, write or lock failure.

Writers hold the lock; readers need none, since they only ever see a whole file.

## Depends on

The standard library only. Add it with `uv add --editable ../../packages/jsonstate`.

## Tests

`uv run --frozen --no-sync pytest`
