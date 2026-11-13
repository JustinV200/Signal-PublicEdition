# mail_digest.announce

Composes a run's one spoken message and sends it through the audiohub CLI. The runner speaks, not the model: the job has no audiohub tools.

## Public API (`from mail_digest.announce import ...`)

- `Announcement(key, sentence)`: one thing to say once, with a stable key.
- `compose(candidates, announced, max_items, more_hint=...)` returns `(text, keys)`. It drops already-announced keys and repeats (`fresh_announcements`), speaks the first `max_items` and adds "Plus N more." and `more_hint` (where to look) for the rest. `keys` covers only the spoken items, so a summed-up one can be spoken on a later run. Returns `("", ())` when nothing is new.
- `send_notify(text, source="mail-digest")` runs `uv run --project tools/audiohub --frozen --no-sync audiohub notify --source <source> --priority high -- TEXT` (the checker's source is `assignment-check`) once through `child_env.run_hidden` (hidden window, clean env, repo-root cwd, 60 s timeout). `--no-sync` because the running hub holds that venv's files. Returns True only on exit 0, so the caller stores keys only when the hub queued the message. Never raises.

## Files

`announcement.py`, `notify.py`.

## Dependencies

`mail_digest.settings`, `mail_digest.child_env`. Standard library only.
