"""Public API of browser_tool.redaction: find secret fields and keep their values out of output."""

from browser_tool.redaction.engine_script import ENGINE_NAME, SENSITIVE_SELECTOR
from browser_tool.redaction.sensitive_fields import (
    is_focus_on_sensitive_field,
    is_sensitive_locator,
    is_sensitive_ref,
    register_sensitive_engine,
    sensitive_masks,
)
from browser_tool.redaction.snapshot_lines import (
    SnapshotLine,
    build_ref_labels,
    indent_of,
    label_of,
    parse_line,
)
from browser_tool.redaction.snapshot_redactor import REDACTED_VALUE, redact_snapshot
from browser_tool.redaction.text_safety import replace_unsafe_chars
from browser_tool.redaction.value_scrub import live_secret_values, replace_values

__all__ = [
    "ENGINE_NAME",
    "REDACTED_VALUE",
    "SENSITIVE_SELECTOR",
    "SnapshotLine",
    "build_ref_labels",
    "is_focus_on_sensitive_field",
    "is_sensitive_locator",
    "indent_of",
    "is_sensitive_ref",
    "live_secret_values",
    "label_of",
    "parse_line",
    "redact_snapshot",
    "register_sensitive_engine",
    "replace_unsafe_chars",
    "replace_values",
    "sensitive_masks",
]
