"""Word tokens with their positions in the original transcript.

The phrase matchers (wake phrase, stop) compare normalised words but
must hand back the user's original text, with its casing and punctuation, to
the brain. So each token keeps the span it came from.
"""

import re
from dataclasses import dataclass

# A run of letters/digits, optionally joined by apostrophes ("what's", "don't").
# [^\W_] is \w without the underscore, so non-ASCII letters count too.
_WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")
_APOSTROPHES = "'’"


@dataclass(frozen=True)
class Token:
    """One word of a transcript.

    Attributes:
        word: Lowercased, with apostrophes removed ("What's" -> "whats").
        start: Index of the word's first character in the original text.
        end: Index just past the word's last character.
    """

    word: str
    start: int
    end: int


def tokenize(text: str) -> list[Token]:
    """Split text into normalised word tokens, ignoring punctuation and spacing.

    Args:
        text: Any transcript.

    Returns:
        The tokens in order; empty when the text has no words.
    """
    return [
        Token(_normalize(match.group()), match.start(), match.end())
        for match in _WORD.finditer(text)
    ]


def words(text: str) -> list[str]:
    """Return just the normalised words of `text`, e.g. "Hey, Claude!" -> ["hey", "claude"]."""
    return [token.word for token in tokenize(text)]


def has_words(text: str) -> bool:
    """Say whether `text` contains at least one word (not just punctuation or space)."""
    return _WORD.search(text) is not None


def _normalize(word: str) -> str:
    lowered = word.lower()
    for apostrophe in _APOSTROPHES:
        lowered = lowered.replace(apostrophe, "")
    return lowered
