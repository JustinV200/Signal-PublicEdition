"""Settings: each tool's editable config values, read and written in its real config files.

Schemas live in data/settings/<tool>.json (see schema.py). The settings setup step and
`setup config` use this package; nothing here prompts (that's steps/settings_step.py).
Public API: load, Schema, Setting, current, default, set_value, leftovers, find,
tool_leftovers, ensure_files, display, is_placeholder, is_prose_file.
"""

from signal_setup.settings.placeholders import is_placeholder, is_prose_file
from signal_setup.settings.schema import Schema, Setting, load
from signal_setup.settings.store import (
    current,
    default,
    ensure_files,
    find,
    leftovers,
    set_value,
    tool_leftovers,
)
from signal_setup.settings.values import display

__all__ = [
    "Schema",
    "Setting",
    "current",
    "default",
    "display",
    "ensure_files",
    "find",
    "is_placeholder",
    "is_prose_file",
    "leftovers",
    "load",
    "set_value",
    "tool_leftovers",
]
