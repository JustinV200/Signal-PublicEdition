"""The checks every text field of a brief entry passes before it's logged.

No control, format, surrogate, private-use, unassigned or line/paragraph-separator
character, and none of the letters and marks that render as nothing. A line break
inside a title could hide a second line on a surface that shows one, and an
invisible character can smuggle bytes past a reader.

The character rule is the one mail-digest's line rules use
(tools/mail-digest/src/mail_digest/kb/line_rules.py, INVISIBLE and the category
check). TODO: mail-digest should import it from here when it becomes a brief
producer (phase 2); its round was in flight when this landed, so it wasn't moved.
"""

import re
import unicodedata

# Unicode categories never allowed: Cc control, Cf format, Cs surrogate, Co private
# use, Cn unassigned, Zl line and Zp paragraph separators.
FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
# Letters and marks that render as nothing: variation selectors, the combining
# grapheme joiner, Khmer inherent vowels, Hangul fillers and the Khitan filler.
INVISIBLE = re.compile(
    "[\ufe00-\ufe0f\U000e0100-\U000e01ef\u180b-\u180d\u180f"
    "\u034f\u17b4\u17b5\u115f\u1160\u3164\uffa0\U00016fe4]"
)
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:|-]{0,119}$")
# How much of a caller's input an error message quotes back.
ERROR_QUOTE_CHARS = 40


def check_text(name: str, value: object, max_chars: int, allow_newlines: bool = False) -> str:
    """`value` if it's a string that passes the rules, else ValueError.

    Args:
        name: The field's name, for the error.
        value: The field's value.
        max_chars: The most characters allowed.
        allow_newlines: Let "\\n" through (multi-line detail).

    Returns:
        The value, unchanged.

    Raises:
        ValueError: Not a string, too long, or a forbidden character.
    """
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    if len(value) > max_chars:
        raise ValueError(f"{name} is {len(value)} characters (at most {max_chars})")
    for char in value:
        if allow_newlines and char == "\n":
            continue
        if unicodedata.category(char) in FORBIDDEN_CATEGORIES or INVISIBLE.match(char):
            raise ValueError(f"{name} has a control or invisible character (U+{ord(char):04X})")
    return value


def check_key(key: str) -> str:
    """`key` if it matches KEY_PATTERN, else ValueError."""
    if not KEY_PATTERN.fullmatch(key):
        raise ValueError(
            f"bad key {key[:ERROR_QUOTE_CHARS]!r}: lowercase letters, digits and _.:|- only"
        )
    return key
