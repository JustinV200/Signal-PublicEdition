# signal_orchestrator (packages/orchestrator)

Reach the claimed Signal orchestrator session: read its claim, and send it a message through Claude Code's cross-session inbox (a Windows named pipe). The console (`tools/console`) sends the owner's typed requests this way, and the voice hub (`tools/audiohub`) sends its hand-offs, so there is one sender. Each tool writes its own wording and marker; this package only delivers.

`console claim` writes the claim file (`tools/console/.state/orchestrator.json`, owner-only). The console owns where that file lives and how it's locked; this package only encodes and reads it.

## Public API (`from signal_orchestrator import ...`)

- `Claim(socket, token, label, claimed_at)`: a claimed session's inbox. The token is kept out of `repr`.
- `claim_from_env(environ, label) -> Claim` builds one from `CLAUDE_CODE_MESSAGING_SOCKET` and `CLAUDE_CODE_MESSAGING_TOKEN` (`SOCKET_ENV`, `TOKEN_ENV`), which Claude Code exports to a session's tools. It raises `ClaimError` when they're missing or the socket isn't a local named pipe.
- `claim_to_json(claim)` is the object the claim file holds. `read_claim_file(path) -> Claim | None` reads it back, and gives None for a missing, unreadable or malformed file. Both checks refuse a socket that isn't `\\.\pipe\...` (`PIPE_PREFIX`) with no `..` or `/`, since the token is written to it.
- `async send_to_inbox(claim, text)` writes the auth line and the message frame, and raises `InboxError` when the pipe can't be opened (3 s) or Claude Code closes the connection within 0.5 s (wrong token, or a frame it rejects). `encode_frames(token, text)` is the bytes it writes.

The auth line is documented ([cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging#the-sessions-inbox-socket)). The message frame isn't: it's the one Claude Code 2.1.301's own sender writes, and it may change in a later version. See `inbox.py`.

Whoever holds the session's token can write any words, so a sender's marker (`[Signal console]`, `[Signal voice]`) is a label, never consent.

## Test helpers (`signal_orchestrator.testing`)

- `fake_inbox(is_refusing=False)`: an async context manager serving a fake inbox on a fresh pipe. It yields a `FakeInbox` with `address`, `received` bytes and `frames()` (the lines as JSON).
- `unused_pipe_address()`: a pipe name nothing serves.

Tests of anything that sends to the orchestrator use these, so they never reach a real session.

## Depends on

The standard library only (asyncio, json). Tools add it with `uv add --editable ../../packages/orchestrator`.

## Tests

`uv run --frozen --no-sync pytest` (Windows only: the fakes are named pipes).
