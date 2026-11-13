# audiohub.kernel.ipc

This package lets other processes, such as the MCP `notify` tool or `audiohub notify`, hand messages to a running hub's kernel.

## Security

Binding to loopback isn't enough on its own, because any web page can POST to `127.0.0.1:8765`. Two rules stop that:
- **A token on every request.** On `start()` the server writes `secrets.token_urlsafe(32)` to `CACHE_DIR / "ipc-token"` (`tools/audiohub/.cache`, gitignored). On POSIX the file is mode 0600; on Windows `icacls` makes it owner-only, best effort. The file is deleted on `close()`. Requests must carry the token, and it is checked with `hmac.compare_digest`. A browser can't read the file.
- **The first invalid line ends the connection.** Bad JSON, a missing or wrong token, or an oversized line gets an error reply and a hang-up. An HTTP request starts with `POST / HTTP/1.1`, so its body is never read.

## Modules

- `auth_token.py` creates, reads, removes and compares the token.
- `protocol.py` defines the wire format. It is newline-delimited UTF-8 JSON, with lines capped at 16 KiB.
  - A request is `{"token": str, "source": str, "text": str, "priority": "urgent"|"high"|"normal"|"low"}`. `priority` is optional and defaults to `normal`.
  - An optional `"ring_through": true|false` (default false) marks a note to be spoken even while the owner is asleep or away, e.g. a Duo heads-up. Only `urgent` notes may set it: a non-urgent note with `ring_through: true` is refused with an error reply (and the connection closed), not downgraded, so a caller's bug shows at once instead of as a note that silently never arrives. The token is still checked first. `encode_request` sends the key only when it is true.
  - A reply is `{"ok": true, "id": "m12"}` or `{"ok": false, "error": "..."}`.
  - A note dropped because the owner is asleep or away gets `{"ok": false, "error": "dropped: the owner is asleep", "dropped": true}` (or `... is away`). `ok` is false so clients that only know `id` count it as not delivered. It is a valid request, so the connection stays open.
  - `{"token": str, "command": "shutdown"}` asks the hub to exit cleanly, as Ctrl+C does (music restored, audio and Claude closed). The reply is `{"ok": true}`. The console's Voice Stop sends it, and kills the hub only if it hasn't exited after 10 s. Any other `command` is rejected.
  - Unknown keys, blank fields and oversized lines are rejected.
- `presence.py` holds `PresenceFiles(sleep_state, away_state)`. `quiet_reason()` returns "the owner is asleep" while sleepmode's `state.json` has `"is_asleep": true`, "the owner is away" while the brief's `away.json` has `"on": true` and an ISO `until` still ahead, else None. The files are read by path, never imported. A missing or unreadable file counts as unset (fail open), so a broken file never silences the hub.
- `server.py` holds `KernelServer(kernel, host, port, token_path=DEFAULT_TOKEN_PATH, *, presence=None)`, an asyncio TCP server.
  - With `presence`, a notification that arrives while the owner is asleep or away is dropped (logged at INFO) instead of submitted, unless it is a `ring_through` note, which is submitted and logged at INFO as having rung through. `None` never drops (tests).
  - `await wait_for_shutdown()` returns once a client sends the shutdown command; `Conversation.run` awaits it to end the hub.
  - It binds IPv4 loopback only.
  - It handles several valid requests per connection and drops a connection after 30 s idle.
  - Writes and closes time out after 5 s, so a client that stops reading can't stall it.
  - It accepts at most 16 connections at once; extra ones get an error reply.
  - `close()` shuts open connections instead of waiting out their idle timeout.
  - Port 0 picks a free port, which you can read back from `.port`.
- `client.py` holds `send_notification(host, port, source, text, priority="normal", *, token_path=DEFAULT_TOKEN_PATH) -> str`, a blocking stdlib client. It reads the token file and raises:
  - `HubNotRunningError` if there is no token file or nothing is listening
  - `NotificationDroppedError` (a `NotificationRejectedError`) if the hub dropped it because the owner is asleep or away; its message is the hub's, e.g. "dropped: the owner is asleep"
  - `NotificationRejectedError` if the hub refuses
  - `ProtocolError` for invalid input

Tests pass a temp `token_path`, so they never overwrite or delete a running hub's token.

## Dependencies

- `..messages` and `..facade.Kernel` from the kernel
- `audiohub.config.CACHE_DIR`
- the standard library
