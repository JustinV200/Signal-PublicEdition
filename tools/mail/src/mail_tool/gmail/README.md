# mail_tool.gmail

A small client for the Gmail REST API (`https://gmail.googleapis.com/gmail/v1/users/me/`), plus the parsing it needs. It has no discovery client and no account storage.

## Public API

- `GmailClient(session, alias)`: `.get(path, params)` and `.post(path, body)` return the JSON object. Failures become `MailError`s with fixed, secret-free messages:
  - A refresh `invalid_grant` raises `ReauthRequired` ("re-run `mail add <alias>`").
  - Any other refresh failure raises `MailError` with the OAuth error code only.
  - A network failure raises `OfflineError`.
  - An HTTP 4xx/5xx raises `GmailError` with Gmail's `error.message` (`GmailNotFound` for a 404).
  - A GET is tried up to 3 times on a network failure or a 429/500/502/503/504, waiting 1 s then 2 s (or `Retry-After`, capped at 10 s). A POST is never retried, so a send can't go out twice.
- `HttpSession`: the protocol it needs (`request(method, url, **kwargs)`). In production this is an `AuthorizedSession`; tests pass a fake.
- `checked_id(value, kind)`: accepts only `[A-Za-z0-9_-]{1,128}`, so an id can't rewrite the URL path.
- `header_map(part)`: maps lower-cased header names to their first value. `header_values(part, name)` returns every value of one header, since a message can repeat To.
- `extract_content(payload) -> MessageContent(text, attachments)`: prefers the first `text/plain` part; otherwise it converts the first `text/html` part. Parts with a file name are listed as `Attachment(filename, mime_type, size)` and never downloaded.
- `html_to_text(html)`: stdlib `html.parser`. It drops script, style, title, noscript and template, turns blocks into line breaks and tidies whitespace.
- `strip_quoted(text)`: removes `>` lines and `On ... wrote:` lines, and cuts a top-posted reply at the `On ... wrote:` line, for the thread view.
- `DraftContent`, `as_reply(content, original_headers)` and `encode_draft(content)`: the RFC 2822 draft with `In-Reply-To`/`References` and the `Re:` subject. Line breaks in headers are refused.

## Depends on

`requests`, `google-auth` (only for its exception types), and `mail_tool.errors`.
