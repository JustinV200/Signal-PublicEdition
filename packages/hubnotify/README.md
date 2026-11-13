# signal_hub_notify (packages/hubnotify)

An asyncio client that hands voice notes to the audiohub hub's kernel (127.0.0.1:8765), so they are spoken into the owner's ears. Shared by the sessions and browser tools. Each tool writes its own wording; this package only delivers.

audiohub owns the wire format: see `tools/audiohub/src/audiohub/kernel/ipc/README.md`. This package doesn't import audiohub, so the tools stay independent. audiohub's own blocking client (`audiohub.kernel.ipc.client`) is still what its CLI and MCP `notify` tool use.

## Public API (`from signal_hub_notify import ...`)

- `HubNote(source, text, priority="normal", ring_through=False)` is one message. `source` names the speaker (at most `MAX_SOURCE_CHARS`, 64, characters, and cut to that on send). `priority` is a `Priority`: `"urgent"`, `"high"`, `"normal"` or `"low"`.
  - `ring_through=True` asks the hub to speak the note even while the owner is asleep or away (for heads-ups the owner must hear, such as Duo). It is sent as `"ring_through": true` only when set. The hub accepts it only on an `"urgent"` note and refuses any other (`HubRejectedError`). The owner may still not answer, so callers must plan for that.
- `async send_to_hub(host, port, note, token) -> str` sends one JSON line `{"source","text","priority","token"}` (plus `"ring_through": true` when set), reads `{"ok": true, "id"}`, and returns the id.
  - It raises `HubUnavailableError` (nothing listening, or the connect timed out after 3 s), `HubRejectedError` (refused, unreadable reply, or a note over 16 KiB) or `TimeoutError` (no reply within 5 s).
  - A note the hub dropped unspoken (`{"ok": false, "error": "dropped: <reason>", "dropped": true}`) raises `HubDroppedError`, a `HubRejectedError` whose `reason` is one of `DROP_REASONS` (`"the owner is asleep"`, `"the owner is away"`). A dropped reply with any other reason is a plain `HubRejectedError`, so a reason a caller shows is always one of those fixed strings.
- `Notifier(host, port, token_file, send=send_to_hub)`:
  - `post(note)` starts delivery in a background task and returns that task at once. Call it from the event loop. Awaiting the task gives the `Delivery`; callers that don't care ignore it.
  - `deliver(note) -> Delivery` delivers now. `drain()` waits for every posted note (shutdown and tests).
  - `Delivery(status, reason=None)`: `status` is a `DeliveryStatus`: `SPOKEN` (the hub took it), `DROPPED` (with the hub's `reason`), `NO_HUB` (no token file or nothing listening) or `FAILED` (refused, unreadable, timed out or another socket error).
  - The token is read from `token_file` at each delivery, because the hub writes a new one each time it starts. A missing file means the hub isn't running.
  - Every failure is logged and reported as a `Delivery`, never raised, so a caller never waits on or fails because of the hub.
  - `send` takes a fake in tests (`SendToHub` is its type).

## Depends on

The standard library only (asyncio, json, logging). Tools add it with `uv add --editable ../../packages/hubnotify`.

## Tests

```
uv run pytest
```

The tests use a fake hub on an ephemeral loopback port and temp token files. They never read the real token file or reach a running hub.
