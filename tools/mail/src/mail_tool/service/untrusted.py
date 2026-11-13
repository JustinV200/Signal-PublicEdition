"""wrap_untrusted: mark email-derived text as data for the model.

Every subject, body, snippet, address header and attachment name the tool
returns goes through here. The tag name is defanged inside the text, so an
email can't close the wrapper early and have its next words read as
instructions. The text is NFKC-normalized first, so fullwidth and other
compatibility forms of the tag (＜／ｕｎｔｒｕｓｔｅｄ…) become plain ASCII and get
caught. Invisible format characters (zero-width spaces and the like) placed
between the tag's letters don't stop the match either.
"""

import re
import unicodedata

TAG = "untrusted_email_content"
OPEN_TAG = f"<{TAG}>"
CLOSE_TAG = f"</{TAG}>"
DEFANGED_TAG_NAME = "untrusted-email-content-tag-removed"
NORMAL_FORM = "NFKC"
# Zero-width space/joiners, LRM/RLM, word joiner, BOM and soft hyphen: Unicode format
# characters (Cf) that NFKC keeps but that render as nothing.
_INVISIBLE = "[​-‏⁠-⁤﻿­]*"
_TAG_NAME = re.compile(_INVISIBLE.join(re.escape(char) for char in TAG), re.IGNORECASE)


def wrap_untrusted(text: str) -> str:
    """Wrap text in <untrusted_email_content>...</untrusted_email_content>.

    Args:
        text: Text that came from an email.

    Returns:
        The NFKC-normalized, defanged text wrapped in the tags, or "" for empty
        text (an empty wrapper says nothing).
    """
    if not text:
        return ""
    normalized = unicodedata.normalize(NORMAL_FORM, text)
    return f"{OPEN_TAG}{_TAG_NAME.sub(DEFANGED_TAG_NAME, normalized)}{CLOSE_TAG}"
