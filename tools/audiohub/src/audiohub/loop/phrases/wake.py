"""Wake-phrase matching: was the user talking to Claude, and what did they ask?

The conversation only sends a transcript to the brain when it starts with a
wake phrase ("Hey Claude, what's the time?") or ends with one after a comma
("What's the time, Claude?"). "Hey Signal" works too; its bare form "Signal"
counts only as that trailing vocative, since "signal" is an everyday word.
Whisper often mishears "Claude" on the noisy narrowband glasses mic, so
common soundalikes are accepted too. Matching is
case- and punctuation-insensitive; the returned request keeps the user's
original wording.
"""

from collections.abc import Sequence

from .tokens import Token, has_words, tokenize, words

# Ways Whisper writes a wake word. Accepted wherever the word sits in a phrase.
_SOUNDALIKES: dict[str, frozenset[str]] = {
    "claude": frozenset({"claude", "claud", "clawed", "clawd", "klaud", "klaude", "clod"}),
    "signal": frozenset({"signal", "cygnal", "signul", "signle", "signel"}),
    "hey": frozenset({"hey", "hay", "hi", "hiya", "heya"}),
}

# Soundalikes that are everyday words on their own ("cloud"), so they are
# accepted only after an earlier word of the phrase matched: "hey cloud" wakes
# Claude, but "cloud storage is down" does not.
_CONTEXT_SOUNDALIKES: dict[str, frozenset[str]] = {
    "claude": frozenset({"cloud", "clouds", "claw", "claws", "clause"}),
    # "signals", "single" and "sigma" are real words: only after "hey".
    "signal": frozenset({"signals", "single", "sigma", "signa"}),
}

# Words people put before a wake phrase without changing its meaning.
_LEADING_FILLERS = frozenset(
    {"ok", "okay", "um", "uh", "er", "erm", "so", "oh", "and", "well", "alright"}
)

# Punctuation and spacing left between the wake phrase and the request.
_SEPARATORS = " \t\r\n,.;:!?-–—…"
_SENTENCE_ENDINGS = "?!."
# A trailing wake phrase counts only after a comma, as in "Thanks, Claude".
_VOCATIVE_COMMA = ","


# Every soundalike mapped to the wake word it stands for, for canonical_words().
_CANONICAL_WORDS: dict[str, str] = {
    soundalike: wake_word
    for table in (_SOUNDALIKES, _CONTEXT_SOUNDALIKES)
    for wake_word, soundalikes in table.items()
    for soundalike in soundalikes
}


def canonical_words(text: str) -> list[str]:
    """The words of `text`, with every wake-word soundalike replaced by the wake word.

    For comparing what the user said with what Claude said, where a misheard
    "Claude" ("Clawed, stop") must still match Claude's own "Claude".

    Args:
        text: Any transcript or spoken text.

    Returns:
        Normalised words, e.g. "Clawed, stop." -> ["claude", "stop"].
    """
    return [_CANONICAL_WORDS.get(word, word) for word in words(text)]


def match_wake(transcript: str, phrases: Sequence[str]) -> str | None:
    """Strip a wake phrase from a transcript, or say the user wasn't addressing Claude.

    Args:
        transcript: One utterance as Whisper wrote it.
        phrases: Wake phrases from the config, e.g. ("hey claude", "claude", "hey signal").
            Longer phrases are tried first, so "hey claude" is stripped whole.

    Returns:
        The request with the wake phrase and its punctuation removed, in the
        user's own words ("" when they said only the wake phrase), or None if
        no wake phrase was found at the start or, after a comma, at the end.
    """
    tokens = tokenize(transcript)
    phrase_words = sorted(
        (words(phrase) for phrase in phrases if has_words(phrase)), key=len, reverse=True
    )
    start = _skip_leading_fillers(tokens)
    for wake_words in phrase_words:
        if _matches_at(tokens, start, wake_words):
            wake_end = tokens[start + len(wake_words) - 1].end
            return _clean_request(transcript[wake_end:])
    for wake_words in _trailing_phrases(phrase_words):
        request = _match_trailing(transcript, tokens, wake_words)
        if request is not None:
            return request
    return None


def _trailing_phrases(phrase_words: list[list[str]]) -> list[list[str]]:
    """Phrases allowed as a trailing vocative: each one, and "hey X" also as just "X".

    "Thanks, Signal" wakes from the "hey signal" phrase, while a bare leading
    "signal" ("signal strength") never does, because the word is too common.
    """
    bare = [words[1:] for words in phrase_words if len(words) > 1 and words[0] == "hey"]
    return sorted(phrase_words + bare, key=len, reverse=True)


def _skip_leading_fillers(tokens: list[Token]) -> int:
    index = 0
    while index < len(tokens) and tokens[index].word in _LEADING_FILLERS:
        index += 1
    return index


def _matches_at(tokens: list[Token], start: int, wake_words: list[str]) -> bool:
    if start + len(wake_words) > len(tokens):
        return False
    return all(
        _is_wake_word(wake_word, tokens[start + offset].word, has_context=offset > 0)
        for offset, wake_word in enumerate(wake_words)
    )


def _is_wake_word(wake_word: str, heard: str, has_context: bool) -> bool:
    if heard == wake_word or heard in _SOUNDALIKES.get(wake_word, ()):
        return True
    return has_context and heard in _CONTEXT_SOUNDALIKES.get(wake_word, ())


def _match_trailing(transcript: str, tokens: list[Token], wake_words: list[str]) -> str | None:
    """Match "<request>, <wake phrase>" and return the request, keeping its final '?'."""
    start = len(tokens) - len(wake_words)
    # start must leave at least one word of request before the wake phrase.
    if start < 1 or not _matches_at(tokens, start, wake_words):
        return None
    gap = transcript[tokens[start - 1].end : tokens[start].start]
    if _VOCATIVE_COMMA not in gap:
        return None
    request = transcript[: tokens[start - 1].end].strip()
    ending = transcript[tokens[-1].end :].strip()
    if ending and ending[0] in _SENTENCE_ENDINGS:
        request += ending[0]
    return request


def _clean_request(rest: str) -> str:
    request = rest.lstrip(_SEPARATORS).rstrip()
    return request if has_words(request) else ""
