# mail_tool.service

What the mail tool does, in one place, for both the MCP server and the CLI.

## Public API

- `MailService(store, open_session, send_gate)`. Each `account` argument is an alias or an email address.
  - `list_accounts()` returns `[{alias, email, status, detail?}]`. The status is `ok`, `needs re-auth`, `offline` (the email then comes from the saved sign-in) or `error`. It's checked with one `users/me/profile` call per account.
  - `search(account, query, max_results=20)` uses Gmail query syntax and returns at most 50 results: `[{id, thread_id, from, to, subject, date, snippet, labels}]`. Each hit's metadata is fetched in parallel (8 workers); a hit deleted since the listing is skipped.
  - `read(account, message_id)` returns the summary fields plus `cc`, `body` (plain text, capped at 20,000 chars), `body_truncated` and `attachments` (names and sizes only).
  - `thread(account, thread_id)` returns `{thread_id, messages}`, oldest first. Quoted earlier mail is stripped from each body, which is then capped at 5,000 chars. Past 30,000 body chars in all, the oldest messages are dropped and `messages_omitted` gives the count.
  - `create_draft(account, DraftContent(to, subject, body), reply_to_message_id=None)` returns `{draft_id, message_id, thread_id}`. A reply sets `threadId`, `In-Reply-To` and `References`. An empty subject becomes `Re: <original>`. `to` is parsed the way send parses it (`recipients.normalized_to`) and refused if any part isn't an address, so every saved draft can be sent.
  - `send_draft(account, draft_id)` re-reads the draft from Gmail and calls `SendGate.check` first. That raises `SendRefused` unless sending is approved. After Allow it re-reads the draft and refuses if its message id changed (the draft was edited while the dialog was open).
  - `send_to_self(subject, body)` sends one plain-text email from the account whose address is `SELF_ADDRESS` to `SELF_ADDRESS`, with no dialog, and returns `{sent, to, message_id}`. `self_send.self_message` checks the text first (subject at most 200 chars, body at most 100,000, no control characters but line breaks and tabs in the body) and raises `MailError` before any network call. Only the CLI's `send-self` calls it; it isn't an MCP tool.
- `SELF_ADDRESS`: `owner.alt@example.com`, the self-only send's fixed recipient and sender.
- `SendGate(is_enabled, ask=signal_confirm.confirm).check(record, message)`, with `confirm_text(record, message, recipients)`.
  - Recipients come from `recipients.draft_recipients`. It reads every To/Cc/Bcc header of the stored draft (repeats included) with `email.utils.getaddresses`. An unreadable or over-long (254+ chars) address, or more than 20 recipients, is refused without a dialog. These checks apply even with `send.confirm` off.
  - The dialog lists each bare address on its own line, in full, then the subject and as many of the first 6 body lines as fit.
  - The whole text stays under the dialog's 2000-char limit, so the dialog never elides it; if the recipients alone don't fit, the send is refused.
  - Deny is the default and the 120 s timeout denies. `is_enabled` is config `send.confirm`.
- `AccountSignIn(store, client_path, run_flow, fetch_email).add(alias, expected_email)` runs `mail add`. It saves nothing if the signed-in address differs from `expected_email`.
- `wrap_untrusted(text)` NFKC-normalizes the text, defangs the tag name inside it (also when zero-width characters are mixed into the name), and wraps it in `<untrusted_email_content>…</untrusted_email_content>`.
- `build_service()` returns the production wiring (`.state/` files, `mail.toml`).

## Trust

Every string that came from an email is wrapped: address headers, subject, snippet, body and attachment names. Ids, labels and the `date`, which is Gmail's own receive time and not the sender's `Date` header, are not. Attachment `mime_type` isn't wrapped either: it must match `type/subtype` (`[a-z0-9.+-]{1,64}` on each side), or it becomes `application/octet-stream`.

## Files

`mailbox.py` (operations), `views.py` (message dicts), `untrusted.py`, `send_gate.py`, `recipients.py`, `self_send.py`, `sign_in.py`, `factory.py`.

## Depends on

`mail_tool.auth`, `mail_tool.gmail`, `mail_tool.config`, `mail_tool.errors`, and `signal_confirm`.
