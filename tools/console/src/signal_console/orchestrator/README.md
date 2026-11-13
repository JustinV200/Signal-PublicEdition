# orchestrator

Which Claude Code session the console talks to, and how it talks to it.

- `claim.py`: `write_claim` and `read_claim` place the claim at `.state/orchestrator.json` (owner-only). Building, encoding and checking a claim is the shared `signal_orchestrator` package's job (`packages/orchestrator`): `claim_from_env` and `read_claim_file` refuse a socket that isn't a local named pipe (`\\.\pipe\...` with no `..` or `/`), since the token is written to it. The voice hub reads the same file to hand jobs off.
- `send_to_inbox(claim, text)` (from `signal_orchestrator`) writes the auth line and the message frame to the session's named pipe, and raises `InboxError` if that fails. The frame format isn't documented; see that package's `inbox.py`.
- `messages.py`: `chat_request` turns typed text into `ConsoleRequest(display_text, orchestrator_text)`, with the `[Signal console]` marker. The marker is a label, not proof of consent: anything holding the session's inbox token can write it. Buttons never reach the orchestrator; the server runs them itself (`signal_console.actions`).

Public API: `signal_console.orchestrator`, which re-exports `Claim`, `ClaimError`, `SOCKET_ENV`, `claim_from_env`, `InboxError`, `encode_frames` and `send_to_inbox` from `signal_orchestrator`. Depends on `signal_orchestrator`, `state_files` and `paths`.
