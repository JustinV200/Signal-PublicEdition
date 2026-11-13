# audiohub.kernel

Every message bound for the user passes through here: brain replies and notifications from other agents. A Sonnet dispatcher decides the order and timing. It passes text through verbatim and condenses only what is too long to listen to, so the user gets all the information without being overwhelmed.

## Public API (`from audiohub.kernel import ...`)

- `OutboundMessage(id, source, text, priority, created_at, is_direct_reply=False)` and `create_message(source, text, priority="normal", *, is_direct_reply=False)`, which assigns a short id such as `m7`. Messages arriving over IPC are never direct replies.
- `Decision(message_id, action, text, reason)`, where `action` is `deliver`, `hold` or `drop`, and `text` is condensed text or None for verbatim.
- `Inbox`: pending messages (FIFO) plus a bounded history of `DeliveredRecord`s.
- `Dispatcher(kernel_settings, backend=None)`:
  - `async decide(pending, recent_delivered) -> list[Decision]`
  - `start()` and `close()`
- `fallback_policy(pending)`: delivers everything, verbatim, in speaking order: Claude's direct replies first, then by priority, FIFO within each group.
- `Kernel(kernel_settings, dispatcher=None)`:
  - `submit(msg)`, which is safe from any thread
  - `async wait_for_work(timeout_s=None) -> bool`
  - `async next_batch() -> list[(message, text_to_speak)]`, called only when the user is free to hear
  - `requeue(messages)`: puts delivered messages whose speech was cut back in front of the pending ones, history records removed
  - `pending_count` and `drain_pending() -> list[OutboundMessage]`
  - `start()` and `close()`, or use it as `async with`
- `KernelServer(kernel, host, port, token_path=..., *, presence=None)`: loopback-only asyncio TCP server that takes newline-delimited JSON `{"token","source","text","priority"}` and replies `{"ok":true,"id":...}`. With `presence` (a `PresenceFiles`) it drops notifications while the owner is asleep or away, except urgent ones sent with `"ring_through": true`, and `{"token","command":"shutdown"}` ends the hub cleanly through `wait_for_shutdown()`. The token is a secret written to `.cache/ipc-token` while the hub runs, and the first invalid line closes the connection, so web pages can't make the hub speak (see `ipc/README.md`).
- `send_notification(host, port, source, text, priority="normal", *, token_path=...) -> str`: blocking client that reads the token file. It raises `HubNotRunningError` when the hub is down (no token file, or nothing listening) and `NotificationRejectedError` when the hub refuses (`NotificationDroppedError` when it dropped the note because the owner is asleep or away).

- `create_token_file(path) -> str`, `read_token(path)`, `remove_token_file(path, token)` and `tokens_match(given, expected)`: the owner-only token file and constant-time check behind `KernelServer`, shared with `audiohub.phone`. `restrict_to_current_user(path)` makes a file owner-only on Windows (best effort); the hub's pid record uses it too.

## How a decision works

1. `next_batch` moves submitted messages into the inbox and calls `Dispatcher.decide`.
   - **Fast path** (a deliberate kernel rule in `dispatch/safeguards.py`, switched by `FAST_PATH_ENABLED`): if every pending message is urgent or a direct reply of at most `max_spoken_words` words that isn't code-heavy, or the only pending message is that short and plain (from anyone) and doesn't repeat the delivered history, they are delivered at once, verbatim, in speaking order, without asking Sonnet. Sonnet's 2-8 s is too slow for spoken replies. The messages still enter the delivered history.
2. `decide` renders the pending messages (id, source, priority, age, word count, text), the recent delivered history (truncated) and the word limit into one JSON request. It sends this to a persistent, tool-less Sonnet session (`dispatch/backend.py`).
3. The reply's structure is checked strictly (`dispatch/decisions.py`). No pending id may appear twice, a reply that decides no pending id at all (such as `{"decisions": []}`) falls back, and missing ids are delivered verbatim. Decisions for ids that aren't pending (stale ones, already delivered) are skipped with a warning.
4. The kernel's fixed rules then override Sonnet where needed (`dispatch/safeguards.py`), so a mistaken or prompt-injected reply can't lose or bury a message:
   - Deliveries are spoken in speaking order (Claude's direct replies, then priority, FIFO within each), whatever order Sonnet listed. Sonnet only advises on condensing and dropping.
   - Urgent messages are always delivered, verbatim.
   - A hold is delivered verbatim: the hub only asks when the user is free to hear.
   - A drop stands only if its reason names a delivered message, from the history Sonnet was shown or from this batch, whose original text it repeats exactly, apart from whitespace and a trailing "." or "!". Otherwise the message is delivered.
   - Condensed text is used only for messages that are long or code-heavy and expect no reply, and only when it is shorter. Over-long accepted text is logged.
5. On a timeout, bad JSON or an SDK error, `fallback_policy` runs instead, so a message is never lost.
6. Held messages (only a custom dispatcher holds) stay pending. `wait_for_work` wakes again after `hold_recheck_s` so they are re-decided.
7. At shutdown, `drain_pending()` returns whatever is still undelivered, and `close()` logs any it finds.

New tunables (`FAST_PATH_ENABLED`, connect and IPC timeouts, the connection cap) are module constants for now, each marked with a TODO to move into `audiohub.config`.

## Layout

- `messages.py`, `inbox.py` and `facade.py` (the `Kernel`)
- `dispatch/`: prompt, reply validation, fallback, the SDK backend and the dispatcher
- `ipc/`: wire protocol, server and client

## Dependencies

- `audiohub.config` (`KernelSettings`) only, from within audiohub
- `claude-agent-sdk`, used by the backend. `Kernel`, `KernelServer` and the dispatcher names load lazily from the package root, so a process that only calls `send_notification` never imports it.

## Tests

`tests/kernel/` uses a fake backend, so no network is needed. For the live Sonnet smoke test, run `AUDIOHUB_LIVE_TESTS=1 uv run pytest tests/kernel/dispatch/test_dispatcher_live.py -s`.
