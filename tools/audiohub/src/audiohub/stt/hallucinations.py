"""Removes text that Whisper invents from silence or noise.

Whisper was trained on subtitled video. On near-silent or noisy input it often
outputs stock phrases such as "Thank you.", "you" or "Thanks for watching!"
(confirmed here: one second of silence through large-v3-turbo gives
" Thank you."). Two rules:
- Outro phrases (YouTube sign-offs, subtitle credits) are never real requests,
  so those sentences are removed wherever they appear.
- Filler phrases ("thank you", "you") could be genuine. The transcript is
  emptied only when every sentence is made of nothing but fillers (repeats
  included), so "Hey Claude, thank you" survives.
Bracketed sound tags such as "[Music]" and music symbols are always removed.
"""

import re

# All phrases are stored in `_normalise` form: lower case, punctuation removed.
OUTRO_PHRASES = frozenset(
    {
        "thanks for watching",
        "thank you for watching",
        "thanks for watching everyone",
        "thank you so much for watching",
        "please subscribe",
        "please like and subscribe",
        "like and subscribe",
        "dont forget to like and subscribe",
        "subscribe to my channel",
        "see you in the next video",
        "subtitles by the amaraorg community",
        "subtitles by amaraorg",
        "transcription by castingwords",
    }
)

FILLER_PHRASES = frozenset(
    {
        "you",
        "thank you",
        "thank you very much",
        "thank you so much",
        "thanks",
        "so",
        "uh",
        "um",
        "hmm",
    }
)

# A sentence made only of fillers, possibly repeated ("you you you", a
# classic Whisper loop). Longest phrases first so the regex matches greedily.
_FILLER_ALTERNATIVES = "|".join(sorted(map(re.escape, FILLER_PHRASES), key=len, reverse=True))
_ONLY_FILLERS = re.compile(rf"(?:{_FILLER_ALTERNATIVES})(?: (?:{_FILLER_ALTERNATIVES}))*")

# "[Music]", "(upbeat music)", "[BLANK_AUDIO]", "♪ la la ♪" and similar.
_SOUND_TAG = re.compile(r"\[[^\]]*\]|\([^)]*\)|[♪♫]+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
_NOT_WORD = re.compile(r"[^\w\s]")
_WHITESPACE = re.compile(r"\s+")


def remove_hallucinations(transcript: str) -> str:
    """Return `transcript` with known Whisper hallucinations removed.

    Args:
        transcript: Raw text joined from Whisper's segments.

    Returns:
        The cleaned transcript with whitespace collapsed, or "" if nothing
        real is left.
    """
    without_tags = _WHITESPACE.sub(" ", _SOUND_TAG.sub(" ", transcript)).strip()
    sentences = [s for s in _SENTENCE_BREAK.split(without_tags) if _normalise(s)]
    kept = [s for s in sentences if _normalise(s) not in OUTRO_PHRASES]
    if all(_ONLY_FILLERS.fullmatch(_normalise(sentence)) for sentence in kept):
        return ""
    return " ".join(kept)


def _normalise(text: str) -> str:
    # Curly apostrophes become straight ones first, then all punctuation goes,
    # so "Don't" and "Don’t" both normalise to "dont".
    lowered = text.lower().replace("’", "'")
    return _WHITESPACE.sub(" ", _NOT_WORD.sub("", lowered)).strip()
