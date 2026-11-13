"""Context window size per model: a small table you can edit.

The transcript's model id never carries the `[1m]` suffix a session was started
with, so the table is the main source. Edit it to match your plan's models, or set
one window for every model: `window_tokens` in contextmeter.toml (what setup writes),
or CONTEXTMETER_WINDOW_TOKENS, which wins over the file.
"""

import os

WINDOW_OVERRIDE_ENV = "CONTEXTMETER_WINDOW_TOKENS"
DEFAULT_WINDOW_TOKENS = 200_000
ONE_MILLION_TOKENS = 1_000_000

# Model id prefix -> window. Longest matching prefix wins. These models ran
# well past 200k tokens in real transcripts, so they have the 1M window here.
# These rows assume the `[1m]` model variant; without it, set the override.
WINDOW_BY_MODEL_PREFIX: dict[str, int] = {
    "claude-opus-5": ONE_MILLION_TOKENS,
    "claude-opus-4-8": ONE_MILLION_TOKENS,
    "claude-sonnet-5": ONE_MILLION_TOKENS,
    "claude-fable-5": ONE_MILLION_TOKENS,
}


def context_window(model: str, used_tokens: int, configured_tokens: int = 0) -> int:
    """Return the context window, in tokens, for `model`.

    Args:
        model: The model id, e.g. "claude-opus-5-5" or "opus[1m]".
        used_tokens: Tokens in context now. If that's already past the table's
            window, the model must have the 1M window, so 1M is returned.
        configured_tokens: contextmeter.toml's `window_tokens`; when positive it
            replaces the table.

    A positive integer in $CONTEXTMETER_WINDOW_TOKENS replaces all of this;
    any other value there is ignored.
    """
    override = os.environ.get(WINDOW_OVERRIDE_ENV, "").strip()
    if override.isdigit() and int(override) > 0:
        return int(override)
    if configured_tokens > 0:
        return configured_tokens
    if "[1m]" in model.lower():
        return ONE_MILLION_TOKENS
    matches = [prefix for prefix in WINDOW_BY_MODEL_PREFIX if model.startswith(prefix)]
    window = WINDOW_BY_MODEL_PREFIX[max(matches, key=len)] if matches else DEFAULT_WINDOW_TOKENS
    return ONE_MILLION_TOKENS if used_tokens > window else window
