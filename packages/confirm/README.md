# signal_confirm (packages/confirm)

The owner's Allow/Deny dialog, shared by the vault, browser, sessions and whiteboard tools. Each tool wraps it in its own `Confirmer`/`Approver` adapter.

## Public API (`from signal_confirm import ...`)

- `confirm(title, message, *, timeout_s=120, arm_delay_s=1.5) -> bool` blocks until the owner answers. It is safe to call from any thread.
- `async confirm_async(...)` takes the same arguments and awaits the child process (`asyncio.create_subprocess_exec`), so it never blocks the event loop. Cancelling it closes the dialog.
- Both return True only for a click on Allow. Deny, Escape, closing the window, the timeout, bad arguments, and a child that can't start, crashes or hangs all return False and log why. Neither ever raises.
- `sanitize_text(text, max_chars)` flattens untrusted text to one safe line. `elide(text, max_chars)` keeps the head and tail around " … ".

`message` lines are separated by `"\n"`, and the caller's line breaks are kept. Within each line, the dialog turns every Unicode C* character (controls, bidi overrides) and Z* character (U+2028 and other separators) into a space and collapses runs of spaces. Runs of blank lines collapse too, and over-long text keeps its head and tail. A `"\n"` inside untrusted text is still a line break, though, so callers that put untrusted text after a label (such as `Origin: ...`) pass it through `sanitize_text` first.

## How it works

The dialog runs in a short-lived child process: `sys.executable -I -m signal_confirm`. It gets the request as JSON on stdin and prints `allow` or `deny`. Only exit code 0 with exactly `allow` counts as yes. Running in a child keeps tkinter off the caller's threads and event loop. If the child hangs past `timeout_s` plus a 15 s start-up grace, the parent kills it and denies.

## Why it looks like this (security)

A topmost native MessageBox that pops up while the owner is typing can be approved by a stray keystroke: "Y", or Enter when Yes has focus. This dialog closes that gap.

- Deny has the focus and is the default button.
- Allow is disabled for `arm_delay_s` after the window appears, so a click aimed at another window can't land on it. The click handler checks the clock as well as the button state.
- Allow has no keyboard shortcut and is not in the Tab order. Return and Space press only the focused button, which is always Deny, so no key sequence (Tab then Space included) can approve. Approving takes a deliberate mouse click.
- Escape, the close button, the timeout and any error inside the dialog all deny.

**Same-user limit.** The dialog stops stray input, and no MCP tool can answer it. It does not stop a determined local process. Any process running as the owner's Windows user can find the window and click Allow (UI Automation, `SendInput`), or tamper with the calling tool's process directly. The model's shell runs as that user, so this is a human gate, not a sandbox. The threat model is in `refdocs/research/password-vault.md`.

## Files

- `launcher.py`: `confirm`, `confirm_async`, child start, deadline and answer parsing.
- `protocol.py`: `DialogRequest` (validated JSON) and the `allow`/`deny` tokens.
- `__main__.py`: the child entry point.
- `dialog.py`: the tkinter window. Only the child imports it.
- `arming.py`: the pure "is Allow armed yet?" check.
- `sanitize.py`: `sanitize_text`, `sanitize_message`, `elide`.

## Depends on

The standard library only (tkinter, subprocess, asyncio). Tools add it with `uv add --editable ../../packages/confirm`.

## Tests

```
uv run pytest                # no window
uv run pytest -m desktop     # also shows a real dialog that denies itself after 1 s
```
