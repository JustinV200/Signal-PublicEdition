"""The <untrusted_page_content> wrapper every page-derived text in a result goes inside.

The model is told to treat whatever is inside as data, never instructions. Page
text that imitates the tags is defused so it can't close the wrapper early.
"""

import re

UNTRUSTED_OPEN = "<untrusted_page_content>"
UNTRUSTED_CLOSE = "</untrusted_page_content>"
# Page text that imitates our wrapper tags is defused so it can't close the wrapper.
_WRAPPER_TAG_RE = re.compile(r"<(\s*/?\s*untrusted_page_content)", re.IGNORECASE)


def wrap_untrusted(text: str) -> str:
    """Wrap page-derived text in the untrusted-content tags, defusing look-alike tags.

    Inline (no added newlines), so short labels can be wrapped mid-sentence.
    """
    defused = _WRAPPER_TAG_RE.sub(r"&lt;\1", text)
    return f"{UNTRUSTED_OPEN}{defused}{UNTRUSTED_CLOSE}"
