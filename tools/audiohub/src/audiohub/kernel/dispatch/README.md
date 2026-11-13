# audiohub.kernel.dispatch

This package holds the Sonnet dispatcher, which decides what to deliver verbatim, condense or drop. The speaking order is set in code.

- `prompt.py` holds `DISPATCHER_PROMPT` (the system prompt), `DecisionRequest`, and `render_request()`, which turns a request into the JSON user turn.
- `decisions.py` holds `parse_decisions()`, the strict structural validator for Sonnet's JSON. It raises `DecisionError` when the reply can't be trusted (bad JSON, wrong shape, an id decided twice), then hands the decisions to the safeguards. A decision for an id that isn't pending, usually one Sonnet saw already delivered in the history, is skipped with a warning instead of throwing the whole reply away. A reply that decides no pending id (only such ids, or an empty list) still raises, so the fallback speaks the pending messages. A pending id the reply left out is delivered verbatim.
- `safeguards.py` holds the kernel's fixed rules.
  - `fast_path_decisions()` runs before Sonnet: when every pending message is urgent or a short, plain direct reply, or the only one is short, plain and not a repeat of the history, all are delivered verbatim in speaking order with no Sonnet call.
  - `apply_safeguards()` overrides Sonnet's decisions afterwards:
    - deliveries come out in `speaking_order`, not Sonnet's order
    - urgent messages are always delivered verbatim
    - holds are delivered verbatim (the hub only asks when the user is free to hear)
    - a drop needs a named delivered message with the same text
    - condensing is allowed only for long or code-heavy messages
- `text_checks.py` holds the heuristics behind the safeguards: `is_near_duplicate()` and `is_code_heavy()`. A repeat must equal the delivered text exactly, apart from whitespace and a trailing "." or "!".
- `fallback.py` holds `speaking_order()` (Claude's direct replies first, then priority, FIFO within each group), shared by every path, and `fallback_policy()`: everything, verbatim, in that order.
- `backend.py` defines the `DispatcherBackend` protocol and `SonnetBackend`:
  - It runs one persistent `ClaudeSDKClient`, warmed up on connect.
  - Connect plus warm-up is capped at `CONNECT_TIMEOUT_S`, and a failed connect is discarded so the next call retries.
  - The session is replaced every 10 decisions and after any failure.
  - It raises `BackendClosedError` after `close()`.
- `sdk_session.py` holds the SDK helpers: the session options, one turn, and a bounded disconnect. The session has no tools, no settings or CLAUDE.md, thinking is off, and transcripts aren't saved.
- `dispatcher.py` holds `Dispatcher`. It wires the pieces together, applies `decision_timeout_s` and falls back on any failure.

## Latency

Measured with the real prompt and 5 messages:
- A fresh `query()` per decision took 5-7 s, because each one spawns the CLI.
- A persistent session took about 2.2 s per decision after a 3 s warm-up.

That gap is why the backend keeps its session open.

## Dependencies

- `..messages` from the kernel
- `audiohub.config.KernelSettings`
- `claude-agent-sdk`
