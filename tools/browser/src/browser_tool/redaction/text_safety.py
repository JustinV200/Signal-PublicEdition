"""Replace characters that can disguise page-supplied text shown to the owner.

Control characters (C0, DEL, C1: newlines included), format characters (bidi
overrides like U+202E, zero-width characters, BOM) and the Unicode line and
paragraph separators can fake extra lines or reorder what a dialog or file name
shows. Used for owner dialogs and download file names.
"""

import unicodedata

UNSAFE_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


def replace_unsafe_chars(text: str, replacement: str) -> str:
    """`text` with each control, format or line/paragraph separator replaced."""
    return "".join(
        replacement if unicodedata.category(char) in UNSAFE_CATEGORIES else char for char in text
    )
