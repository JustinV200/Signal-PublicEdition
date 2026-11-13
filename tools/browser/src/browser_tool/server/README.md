# browser_tool.server

The MCP server (stdio) and the `browser-tool` entry point.

## Public API (`from browser_tool.server import ...`)

- `main(argv=None)` is the `browser-tool [--config PATH] [--backend local|docker]` entry point.
  - It logs to stderr, because stdout carries the MCP protocol.
  - It wires `DialogConfirmer` and, through `build_context`, the backend's pieces.
  - It exits with code 2 on a bad config.
- `build_context(backend, settings, confirmer) -> ActionContext` (`wiring.py`).
  - `local` (the default): the desktop profile and `LazyVaultFiller`.
  - `docker`: a `DockerBackend`, `MissingVaultFiller("vault fills are off in docker jobs")` (the vault is never imported), the policy with the container block, `NO_VAULT_PASSWORD_REFUSAL`, `has_vault=False` (the signed-out note doesn't point at `fill_login`) `uploads_allowed=False` (`upload_file` refuses; the server doesn't register it) and `downloads_readable=False` (the same for `read_download`).
- `build_server(ctx, *, is_docker=False) -> MCPServer` registers the tools. Its lifespan closes the browser on shutdown.
  - The desktop server is `browser` (`INSTRUCTIONS`, which also say downloads are saved and reported, never opened, never to sign out or clear cookies, and to `fill_login` only when a page actually asks to sign in). Both servers' instructions say to call `wait_for_duo()` while the owner approves Duo.
  - With `is_docker` it is `browser-docker` (`DOCKER_INSTRUCTIONS`: a throwaway container, no saved logins, downloads refused, never type passwords or codes). It has no `list_credentials`, `fill_login`, `upload_file` or `read_download`, and its `type_text` description doesn't point at `fill_login`.
- `ToolRunner(ctx).run(tool_name, action, *args)` is what every tool calls.
  - It runs one action at a time.
  - It runs the action through `session.run_unless_dialog`: a dialog that freezes the current tab without opening during an act (a confirm opened by a hover, or by a page timer during `wait_for`) cancels the call with `STOPPED_BY_DIALOG` instead of hanging.
  - Before each action it calls `session.end_stale_job()`. After each, it re-arms `IdleClose` (`idle_close.py`), which closes the session after the backend's `idle_close_s` without a tool call (docker: `[browser] idle_close_min`, default 15). The timer is cancelled while a call runs, and a close that fired just as a call started is skipped.
  - `BackendError` messages (Docker not running, image missing or stale, container didn't start) are returned like `ActionError` ones.
  - It maps errors to safe text (`ActionError`, generic Playwright reasons, `INTERNAL_ERROR`). Raw exception text is never returned or logged.
  - After the action, success or error, it appends `actions.download_notes`: each download that finished (saved path, size and original name in `<untrusted_page_content>`, or why it wasn't saved), after waiting up to 60 s for the ones this call started (older running ones are reported later). Then `actions.dialog_notes`: alerts accepted, file pickers a page opened by itself, and every open dialog with how to answer it. Both go before the scrub, since file names and dialog messages are page data.
  - For every open tab, it replaces the live values of all secret fields (`redaction.live_secret_values`, all tabs and frames read together, retried while a navigation commits), then applies the vault's `scrub(page, text)`, through `actions.scrub_secrets`, which the snapshot cache shares. If either fails, the text is replaced by `SCRUB_FAILED`, or by `SCRUB_FAILED_AFTER_ACTION` when the action itself succeeded (so the model doesn't repeat a send). When one tab's read failed or timed out (`actions.TabReadError`), the message names it and suggests `close_tab(N)`.
  - After the scrub, it appends the Duo watcher's queued notices (`await session.duo.take_notices()`, each ending with its voice ping line), so the first result after a tab enters a Duo prompt tells the model, outside `<untrusted_page_content>`, even when the text was withheld. Notices hold only fixed text, a tab index, a hostname made of `[a-z0-9.-]` only (anything else reads "a login") or the owner's `[duo] site_names` name for it, a fixed voice ping line and, on `[duo] code_relay_sites` sites, the prompt's Verified Push code as 3 to 6 ASCII digits. The site picks its own hostname, so the name can still spell words, but it never carries page text, markup or field values.
  - Failures are raised as the SDK's `ToolError`, so the result has `is_error=True`.

## Tools

| Tool | Arguments | Result |
|---|---|---|
| `navigate` | `url` | final URL (no query) and any blocked hops, or that the URL started a download |
| `snapshot` | `ref=None`, `page=1` | one page of the redacted aria snapshot with refs (or of one ref's subtree), in `<untrusted_page_content>`, then `page N of M`; later pages and subtrees come from the tab's cached snapshot |
| `find` | `text`, `max_results=20` (capped at 100) | matching lines of the cached redacted snapshot with line, page, ref and ancestors, in `<untrusted_page_content>`, then the match count |
| `wait_for` | `text`, `gone_ref`, `url_contains`, `network_idle=false`, `timeout_s=10` (capped at 30) | read only: "waited N s for: ...; now at <url>" or "still waiting after N s for: <unmet>; now at <url>; call wait_for again or take a snapshot()" (both plus block and signed-out notes); URLs are shown path-decoded and scrubbed |
| `click` | `ref`, `button="left"`, `double=false`, `modifiers=[]` | what was clicked and where the tab is now; sensitive clicks wait for the owner, whatever the button or modifiers |
| `click_at` | `x`, `y` | the element clicked at the point and where the tab is now; gated like `click` on the deepest element there (through iframes) |
| `drag` | `source`, `target` | what was dragged where; gated on the stricter of the two ends |
| `hover` | `ref` | what the mouse is over; never asks |
| `scroll` | `ref=None`, `direction="down"`, `amount=1` (screens, up to 10) | the visible range in px and whether more content loaded at the end; never asks |
| `type_text` | `ref`, `text`, `append=false`, `slowly=false` | characters typed or added; refuses password/OTP fields; never presses Enter or Tab |
| `select_option` | `ref`, `value` (or a list) | selected values; gated on every option |
| `press_key` | `key` | key pressed; keys that buy, send, delete or submit a login form wait for the owner |
| `back`, `forward` | - | where the tab is now, or "no previous page" / "no next page"; one that would send a form again waits like a send |
| `reload` | - | where the tab is now; refused on a Duo tab; sending a form again waits like a send |
| `tabs` | - | index, URL, title per tab |
| `switch_tab` | `index` | the new current tab |
| `new_tab` | `url` | the new tab's index and where it landed (navigate's policy) |
| `close_tab` | `index` | the tab closed and the current tab; the only tab can't be closed |
| `screenshot` | `ref`, `full_page` | PNG path only (secret fields masked in every frame); the viewport, the whole page or one element |
| `wait_for_duo` | `timeout_s=90` (capped at 300), `wait_anyway=false` | read only: "Duo approved; now at <url>" (plus the signed-out note on a login page), the timeout text with the voice ping line, the dropped-ping text (only from a hub without ring-through; returns at once unless `wait_anyway`), `no Duo prompt on this tab` or `the tab closed` |
| `answer_dialog` | `accept`, `text=None` | "accepted/dismissed the <kind> dialog" and where the tab is now; accepting one whose message or opening action buys, sends or deletes waits for the owner; `text` only on a prompt, refused when it asks for a password, PIN or code |
| `upload_file` | `ref`, `path` | "uploaded <name> (N bytes) through <label>" and where the tab is now; always waits like a send; desktop only |
| `read_download` | `path`, `pages` | a saved PDF's pages ("3" or "2-5", at most 20) or a text file's text in `<untrusted_page_content>`, capped, and what was read; desktop only |
| `list_credentials` | - | id, label, origins, username hint, or `vault not installed` |
| `fill_login` | `credential_id`, `submit=false` | `ok`, `failed: <code>` or `vault not installed` |

While the current tab shows a Duo prompt, `click`, `click_at`, `drag`, `hover`, `scroll`, `type_text`, `select_option`, `press_key`, `reload`, `answer_dialog`, `upload_file`, `fill_login`, `find`, `wait_for` and `screenshot` refuse (see `browser_tool.duo`). While it has a dialog open, every tool but `answer_dialog`, `tabs`, `switch_tab`, `new_tab`, `close_tab`, `list_credentials`, `wait_for_duo` and `read_download` (which reads a saved file, not the tab) refuses it. `wait_for_duo` is on both servers.

`navigate`, `back`, `forward`, `reload`, `new_tab`, `click`, `click_at`, `drag`, `press_key` and `wait_for_duo` end with a signed-out note when the tab ends on a page with a visible password field, and `fill_login` refuses a third fill on a site within 10 minutes (see `browser_tool.actions`, "Sign-ins").

## Files

- `main.py`: argument parsing and logging.
- `wiring.py`: `build_context` for each backend.
- `app.py`: `build_server` and the server instructions.
- `idle_close.py`: the quiet-spell timer.
- `tools/`: the typed tool wrappers, by kind (`navigation_tools.py`, `page_tools.py`, `pointer_tools.py`, `action_tools.py`, `credential_tools.py`); `register_tools` in its `__init__.py`; see `tools/README.md`. Their docstrings are the tool descriptions.
- `tool_runner.py`: serialization, error mapping and scrubbing.

## Dependencies

`mcp` (v2 `MCPServer`), `playwright` (error types) and `browser_tool.actions`, `backends`, `config`, `credentials`, `gates`.
