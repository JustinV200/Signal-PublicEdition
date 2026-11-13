"""Public API of signal_brief.compose: compose a brief and render it for a surface."""

from signal_brief.compose.brief import (
    BRIEF_ID_HASH_CHARS,
    BRIEF_KINDS,
    SECTION_LABELS,
    Brief,
    compose,
)
from signal_brief.compose.render import (
    BRIEF_TAG,
    MAX_HOOK_CHARS,
    MAX_MODEL_CHARS,
    MAX_TEXT_CHARS,
    Render,
    entry_model_data,
    render_model,
    render_text,
)

__all__ = [
    "BRIEF_ID_HASH_CHARS",
    "BRIEF_KINDS",
    "BRIEF_TAG",
    "MAX_HOOK_CHARS",
    "MAX_MODEL_CHARS",
    "MAX_TEXT_CHARS",
    "SECTION_LABELS",
    "Brief",
    "Render",
    "compose",
    "entry_model_data",
    "render_model",
    "render_text",
]
