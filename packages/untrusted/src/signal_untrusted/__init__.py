"""Public API of signal_untrusted: frame outside text as data before a model reads it."""

from signal_untrusted.frame import TAG_PATTERN, frame, framed, safe_json

__all__ = ["TAG_PATTERN", "frame", "framed", "safe_json"]
