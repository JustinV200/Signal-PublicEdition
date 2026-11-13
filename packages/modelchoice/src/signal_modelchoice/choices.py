"""The fixed lists a model or effort pick is chosen from.

The console's pickers send an index into these lists, never a free string, and
the voice brain checks brain-choice.json against them on read, so both sides
share this one copy.
"""

# Claude Code's documented model aliases (code.claude.com/docs model-config).
MODEL_ALIASES: tuple[str, ...] = (
    "default",
    "best",
    "fable",
    "opus",
    "sonnet",
    "haiku",
    "opus[1m]",
    "sonnet[1m]",
    "opusplan",
)

# Effort levels a settings file accepts; `max` is session-only, so it isn't offered.
EFFORT_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh")
