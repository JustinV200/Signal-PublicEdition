# signal_brief.store

The brief's lock and the atomic JSON state files every other part writes through. The file helpers and the lock itself live in the shared `signal_jsonstate` package (`packages/jsonstate`); this folder only binds them to the brief's paths.

- `state_lock(paths)`: context manager holding `.state/events.lock` through `signal_jsonstate.state_lock` (up to 2 s). Not re-entrant: code holding it calls the `*_locked` functions. Raises `BriefLogError`.
- `BriefLogError`: `signal_jsonstate.StateFileError` under the brief's name.
- `read_json_object`, `read_bytes_retrying`, `write_json_atomic`, `write_text_atomic`: re-exported from `signal_jsonstate`.

Depends on: `signal_brief.paths`, `signal_jsonstate`.
