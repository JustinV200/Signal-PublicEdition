# notify

The wording of the voice notes sent about sessions to the audiohub hub's kernel (127.0.0.1:8765). Delivery is done by `signal_hub_notify` (`packages/hubnotify`): the daemon builds one `Notifier` for the hub's address and token file, and it posts each note in the background, reading the token from `tools/audiohub/.cache/ipc-token` at each delivery. If the hub isn't running, the note is logged and dropped, so a session never waits on the hub.

- `turn_finished_note`: normal priority, "OtherRepo session finished: <first 2 sentences>".
- `session_failed_note`: high priority.
- `approval_needed_note`: high priority.
- `source_for(repo)`: the source is `session:<repo>`, cut to 64 characters.

Each returns a `signal_hub_notify.HubNote`.

Depends on: `text`, and `signal_hub_notify` for `HubNote`.
