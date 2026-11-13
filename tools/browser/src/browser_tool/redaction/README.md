# browser_tool.redaction

Keeps password, OTP and similar field values out of everything the model sees.

Playwright 1.64's `aria_snapshot()` prints input values verbatim, password fields included. This package post-processes every snapshot and masks those fields in screenshots.

## Public API (`from browser_tool.redaction import ...`)

- `register_sensitive_engine(playwright)` registers the `signal-sensitive` selector engine.
  - It runs in Playwright's isolated world, so page scripts can't tamper with it.
  - Call it once per Playwright instance, before creating the context.
- `SENSITIVE_SELECTOR` (`"signal-sensitive=any"`) matches secret fields:
  - `type=password`
  - an `autocomplete` of `current-password`, `new-password`, `one-time-code`, `cc-number` or `cc-csc`
  - password, PIN, OTP, 2FA or CVV hints in the name, id, label, placeholder or title
  - CSS `-webkit-text-security` masking
  - The engine searches open shadow roots too.
- `is_sensitive_ref(page, ref)` checks one aria ref. A ref that no longer resolves counts as sensitive.
- `is_sensitive_locator(page, locator)` checks one element.
- `is_focus_on_sensitive_field(page)` checks the focused element in every frame. It uses the engine's `focused` selector body, which reads `activeElement`, so it works even when the window isn't focused.
- `sensitive_masks(page)` returns one locator per frame, for `page.screenshot(mask=...)`.
- `redact_snapshot(text, is_sensitive)` is async.
  - It replaces the value of each sensitive input line with `"[redacted]"` and drops the lines nested under it.
  - It decides by the underlying element, not the aria role, because a password input can be exposed as `button`, `generic` or `slider`. Every ref line that shows a value or nested lines is checked.
  - It fails closed: a failed check gets redacted, and an item line it can't parse gets dropped.
  - An element line with no ref that shows a value is always redacted, because there is no element to check. Ai mode gives refs only to interactable elements, so a zero-size or `pointer-events:none` password field has none. Plain `text:` lines are kept.
- `live_secret_values(page)` reads the live value of every sensitive field in every frame (frames read together; on a Playwright error, such as a navigation destroying the frames, it waits for the new document and retries, 3 tries in all). `replace_values(text, values)` replaces each occurrence in `text` with `[redacted]`.
  - It also matches the whitespace-collapsed, JSON-escaped (ASCII and non-ASCII) and YAML-quoted forms a snapshot prints, including a JSON-escaped name inside a YAML-quoted key.
  - Values under 3 characters are skipped.
  - It catches values that reach text another way, such as an `aria-labelledby` name built from a password input, or a label that contains one.
  - `live_secret_values` raises on an unreadable frame, so callers must withhold the text.
  - URLs are scrubbed in the form tools show them (`actions.secret_scrub.shown_url`: origin plus path, scrubbed, then percent-decoded and scrubbed again), so a secret Edge encoded in the path (`%20`, `%C3%A4`) is found, and so is one that holds its own `%XX`.
  - Known gap: a double-encoded (`%2520`) or `+`-for-space secret in a path isn't caught, and a hostile page can encode secrets any way it likes.
  - Known gap: a secret that contains `?` or `#` is split by the URL into the path and the query or fragment. Only the path is shown and scrubbed, so the part before the `?` or `#` (a prefix of the secret) can show in the path.
- `parse_line(line) -> SnapshotLine | None`, `indent_of(line)` and `build_ref_labels(lines)` parse the snapshot. The labels map each ref to a short label such as `button "Buy now"` (`label_of(line)`).

## Files

- `engine_script.py`: the selector engine JavaScript. This is the single definition of "sensitive field".
- `sensitive_fields.py`: the Playwright helpers.
- `snapshot_lines.py`: the line parser. It handles YAML single and double quoting.
- `snapshot_redactor.py`: the redaction pass.
- `value_scrub.py`: the live-value scrub applied to every tool result.
- `text_safety.py`: `replace_unsafe_chars(text, replacement)`, for page text shown to the owner (dialogs, download file names) and decoded URL paths shown to the model: control, format (bidi, zero-width) and line/paragraph separator characters.

## Dependencies

`playwright` (async API). No other browser_tool packages.
