"""Turn Claude's markdown-flavoured replies into plain text worth speaking.

First stage of the speech front end (`clean_for_speech` -> `split_sentences`
-> `Synthesizer`). Speech can't show formatting and shouldn't read code or
URLs aloud. So this strips markdown, replaces code blocks and links with short
spoken stand-ins, and ends headings and list items as their own sentences so
the voice pauses between them. Line-level structure lives in `blocks.py`.
"""

import re

from audiohub.tts.blocks import join_blocks

CODE_PLACEHOLDER = "code omitted"
LINK_PLACEHOLDER = "a link"

# An opening ``` or ~~~ fence, then everything up to a closing fence of the
# same character that is at least as long (as in CommonMark). A backtick
# opener's info string can't contain backticks, so a line that starts with an
# inline span like ```x``` isn't taken for a fence. An unclosed fence (e.g. a
# reply cut off mid-stream) runs to the end.
_FENCED_CODE = re.compile(
    r"^[ \t]*(?P<fence>(?P<char>[`~])(?P=char){2,})(?!(?<=`)[^\n]*`)[^\n]*(?:\n|\Z)"
    r".*?(?:^[ \t]*(?P=fence)(?P=char)*[ \t]*$|\Z)",
    re.MULTILINE | re.DOTALL,
)
_AUTOLINK = re.compile(r"<(?:https?://|www\.)[^>\s]*>")
# Parentheses in a URL count only in balanced pairs, as in wiki links like
# ".../Foo_(bar)", so "(see https://x.io)" keeps its closing bracket. A URL
# may not end in punctuation or emphasis markers, so "see https://x.io." keeps
# its full stop and "**https://x.io**" its closing "**". Backticks end a URL,
# so one inside an inline code span leaves the span's closing backtick alone.
_BARE_URL = re.compile(r"(?:https?://|www\.)(?:[^\s<>()`]|\([^\s<>()`]*\))*(?<![.,;:!?'\"\]}*_~])")
# Single-backtick spans only. Any stray backticks are dropped at the end.
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# A link target "(...)" may hold one level of balanced parentheses.
_LINK_TARGET = r"\((?:[^()\n]|\([^()\n]*\))*\)"
_IMAGE = re.compile(r"!\[([^\]\n]*)\]" + _LINK_TARGET)
_LINK = re.compile(r"\[([^\]\n]+)\]" + _LINK_TARGET)
# Inline code spans are swapped for these tokens while emphasis is stripped.
# Private-use characters never occur in real replies and aren't word
# characters, so emphasis like **`x`** still matches around a token.
_CODE_TOKEN_START = ""
_CODE_TOKEN_END = ""
_CODE_TOKEN = re.compile(f"{_CODE_TOKEN_START}(\\d+){_CODE_TOKEN_END}")
# Emphasis content can't start or end with its own marker or a space, so
# rules like "___" and "*****" survive for blocks.py to drop. Underscore
# emphasis also needs non-word characters around it, so snake_case names keep
# their underscores; single asterisks get the same guard so "2*3*4" stays.
_EMPHASIS = (
    re.compile(r"\*\*(?=[^\s*])(.+?)(?<=[^\s*])\*\*"),
    re.compile(r"(?<!\w)__(?=[^\s_])(.+?)(?<=[^\s_])__(?!\w)"),
    re.compile(r"~~(?=[^\s~])(.+?)(?<=[^\s~])~~"),
    re.compile(r"(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])"),
    re.compile(r"(?<!\w)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!\w)"),
)


def clean_for_speech(text: str) -> str:
    """Convert markdown text into a single line of plain, speakable prose.

    - Fenced code blocks become "code omitted".
    - URLs become "a link", and markdown links and images keep only their text.
    - Bold, italics, strikethrough, headings, bullet and number markers,
      blockquote markers and inline backticks are stripped (inline code keeps
      its content).
    - Headings, list items and paragraphs each end with sentence punctuation,
      so they're spoken as separate sentences.

    Args:
        text: Raw reply text, possibly containing markdown.

    Returns:
        The cleaned text with whitespace collapsed. Empty if nothing speakable
        is left.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _FENCED_CODE.sub(f"\n\n{CODE_PLACEHOLDER}\n\n", text)
    text = _replace_links(text)
    text = _strip_emphasis_outside_code(text)
    return join_blocks(text.split("\n"))


def _replace_links(text: str) -> str:
    """Swap markdown links and images for their text, and URLs for "a link".

    Markdown links go first, so the bare-URL pattern never sees their
    "](...)" syntax. A link whose text is itself a URL still ends up as
    "a link".
    """
    text = _AUTOLINK.sub(LINK_PLACEHOLDER, text)
    text = _IMAGE.sub(r"\1", text)
    text = _LINK.sub(r"\1", text)
    return _BARE_URL.sub(LINK_PLACEHOLDER, text)


def _strip_emphasis_outside_code(text: str) -> str:
    """Drop emphasis markers and backticks, leaving inline code content as-is.

    Code spans are swapped for tokens first, which protects their content (in
    `__init__.py` the underscores are part of the name, not emphasis) while
    still letting emphasis that wraps a span, like **`x`**, be stripped.
    """
    # Drop any token characters already in the text, so they can't collide.
    text = text.replace(_CODE_TOKEN_START, "").replace(_CODE_TOKEN_END, "")
    spans: list[str] = []

    def stash(match: re.Match[str]) -> str:
        spans.append(match.group(1))
        return f"{_CODE_TOKEN_START}{len(spans) - 1}{_CODE_TOKEN_END}"

    text = _INLINE_CODE.sub(stash, text)
    for pattern in _EMPHASIS:
        text = pattern.sub(r"\1", text)
    text = text.replace("`", "")
    return _CODE_TOKEN.sub(lambda match: spans[int(match.group(1))], text)
