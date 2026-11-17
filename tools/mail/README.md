# mail

Claude's own Gmail tool for the owner's Google accounts: personal Gmail and the school's Google Workspace. Claude can search, read and draft mail through an MCP server (`mail mcp`, server name `mail`). Sending a draft takes the owner's click in an Allow/Deny dialog. The `mail` CLI covers sign-in and account management, plus search and read, and `mail send-self`, which emails the owner's own address with no dialog (see Security).

It calls the Gmail REST API directly with `google-auth`'s `AuthorizedSession`. There's no discovery client.

## Setup

Follow **[SETUP.md](SETUP.md)**. It covers the Google Cloud project, the consent screen (published to production), the Desktop OAuth client JSON at `.state/google_client.json`, and one `mail add` per account. Run `uv run --project tools/mail mail setup` at any time for the short version and a check of the client file.

Register the MCP server in the repo root's `.mcp.json`. The key must be `mail`, because it sets the `mcp__mail__` tool prefix.

```json
{
  "mcpServers": {
    "mail": {
      "command": "uv",
      "args": ["run", "--env-file", ".env", "--project", "tools/mail", "--frozen", "mail", "mcp"]
    }
  }
}
```

The root `.gitignore` needs:

```
tools/mail/.state/
```

## MCP tools

| Tool | Does |
|---|---|
| `mail_accounts` | Lists aliases, emails and status: `ok`, `needs re-auth`, `offline` or `error` |
| `mail_search(account, query, max_results=20)` | Runs a Gmail query (`is:unread newer_than:1d`, `from:x`, `subject:y`) and returns id, thread_id, from, to, subject, date, snippet and labels |
| `mail_read(account, message_id)` | Returns the headers, the body as plain text (HTML converted, capped at 20,000 chars) and attachment names and sizes, without downloading them |
| `mail_thread(account, thread_id)` | Returns the conversation, oldest first, with quoted earlier mail stripped, each body capped at 5,000 chars and the oldest messages dropped past 30,000 chars |
| `mail_draft(account, to, subject, body, reply_to_message_id="")` | Saves a draft and never sends. Replies get `threadId`, `In-Reply-To`, `References` and the `Re:` subject |
| `mail_send_draft(account, draft_id)` | Sends a draft only after the owner clicks Allow |

`account` is an alias (`personal`) or the email address.

## CLI

```
mail setup | add ALIAS [--email ADDRESS] | accounts | remove ALIAS
mail search ACCOUNT QUERY [--max N] | read ACCOUNT ID | mcp
mail send-self --subject SUBJECT --body-file FILE
```

`send-self` emails a UTF-8 text file to `SELF_ADDRESS` (your Gmail address, which setup writes into `service/self_send.py`) from the saved account with that same address, whatever its alias, with no dialog. It prints `Sent to ... (message <id>).` and exits 0, or prints `mail: error: ...` and exits 2 (no saved account for that address, a refused subject or body, Gmail or network trouble). mail-digest's runner calls it after each run.

## Security

- **Scopes**: `gmail.readonly` and `gmail.compose`. Claude can't delete mail, change labels or touch settings. Compose does let it send, which is why sending is gated.
- **Tokens at rest**: each account's refresh token is in `.state/accounts/<alias>.bin`, encrypted with Windows DPAPI (CurrentUser, with tool-specific entropy). Each save is atomic: a temp file in the same folder is made owner-only (icacls, inheritance removed) before the ciphertext goes in, fsynced, then `os.replace`d into place. Access tokens are never written to disk.
- **No secrets out**: refresh tokens and the client secret never appear in tool results, CLI output, logs or exception messages.
  - Records and client configs leave them out of `repr()`.
  - Library auth errors are replaced with fixed messages (`from None`).
  - An expired or revoked sign-in (`invalid_grant`) says "re-run `mail add <alias>`".
  - Any other crash reaches the model only as "Error executing tool".
- **Untrusted content**: every email-derived string (from/to/cc, subject, snippet, body, attachment names) is wrapped in `<untrusted_email_content>…</untrusted_email_content>`, and copies of that tag inside the email are defanged, after NFKC normalization (so fullwidth forms are caught) and allowing for zero-width characters. Attachment MIME types are passed through only if they're a plain `type/subtype`. The server instructions and every reading tool's description tell the model that this is data, never instructions. `date` is Gmail's own receive time, not the sender's `Date` header.
- **Sending**: `mail_send_draft` opens the shared `signal_confirm` dialog.
  - The dialog shows the account, then every To/Cc/Bcc address of the draft as Gmail stores it, each bare address in full on its own line, then the subject and the start of the body.
  - More than 20 recipients, or any address that can't be parsed, is refused without a dialog.
  - If the draft changes while the dialog is open (Gmail gives it a new message id), the send is refused.
  - Deny is the default, Allow needs a mouse click, and no answer within 120 s denies.
  - Set `send.confirm = false` in `.state/mail.toml` to turn this off (not recommended).
  - Like every `signal_confirm` gate, this is a human gate, not a sandbox: a process running as the owner can click Allow or edit `mail.toml`.
- **Self-only send** (`mail send-self`, `service/self_send.py`): the one send with no dialog, and it stays that way because nobody else can receive it.
  - The recipient is the constant `SELF_ADDRESS` (the placeholder `owner.alt@example.com` until setup writes your Gmail address there), and the sending account is the saved account with that same address. There's no recipient argument, and no env var or config key is read for one; a `mail.toml` key for one is refused like any unknown key. So the mail only ever goes from that mailbox to itself.
  - The message is one `text/plain` part with no attachments. The subject is at most 200 chars and the body at most 100,000. Neither may have a control character, except line breaks and tabs in the body. Nothing is stripped or escaped: anything else is refused before Gmail is called.
  - It's CLI-only, not an MCP tool, so the model can't call it. Its caller is trusted code (mail-digest's runner).
  - It needs that address signed in (setup signs it in as `personal`). Without it, it fails with "No mail account" and sends nothing.
- **Sign-in listener**: `mail add` uses google-auth-oauthlib's one-shot redirect server. It binds `127.0.0.1` on a random port, serves one request, and is protected by OAuth `state` and PKCE rather than a token file (see `auth/browser_flow.py`). It runs only while the owner is signing in.

## Layout

`src/mail_tool/` holds `config/`, `auth/`, `gmail/`, `service/`, `mcp_server/` and `cli/`, each with its own README, plus `errors.py`. Dependencies point downward: cli and mcp_server use service, service uses gmail and auth, and everything uses config and errors.

Dependencies:

- `google-auth`: credentials, refresh, `AuthorizedSession`.
- `google-auth-oauthlib`: the installed-app flow.
- `requests`: the transport.
- `mcp==2.3.0`: the same pin as the other tools.
- `signal-confirm`: `packages/confirm`.

## Development

```
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
```

The tests use a fake Gmail HTTP session, a fake dialog and a fake browser flow, and make no network calls. `tests/cli/test_send_self.py` runs the real CLI and `build_service` over fake accounts and a fake Gmail, and checks that no argument, env var or config key changes send-self's recipient. The DPAPI test runs on Windows only. `tests/mcp_server/test_stdio.py` spawns the real `.mcp.json` command. The live OAuth sign-in and the real dialog are tested by hand.
