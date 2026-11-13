"""Split speakable text into sentence-sized chunks for streaming synthesis.

Second stage of the speech front end (`clean_for_speech` -> `split_sentences`
-> `Synthesizer`). The voice output synthesizes one chunk while the one before
it plays, so short chunks mean the first words are heard sooner. Chunks break
after `.`, `!` and `?`, but not after abbreviations ("Mr.", "e.g.") or inside
numbers ("3.5"). A sentence longer than `max_chars` is broken at a clause
boundary, a word boundary, or (as a last resort) mid-word.
"""

import re

DEFAULT_MAX_CHARS = 250
# A clause break leaving a chunk shorter than this fraction of max_chars is
# passed over for a word break nearer the limit, to avoid choppy tiny chunks.
MIN_CLAUSE_FRACTION = 0.4

# Ending punctuation plus any closing quotes or brackets, before a space.
# The text is whitespace-normalised first, so a space is the only separator.
_SENTENCE_END = re.compile(r"[.!?]+[\"')\]}”’»]*(?= )")
_CLAUSE_BREAK = re.compile(r"[,;:—–](?= )")
# Initials and dotted abbreviations: "J.", "e.g.", "i.e.", "U.S.", "a.m.".
_DOTTED_ABBREVIATION = re.compile(r"(?:[A-Za-z]\.)+")
# Abbreviations that almost never end a sentence. Ones that often do
# ("etc.", "Inc.", "No.") are left out, so a split there still happens.
_TITLE_ABBREVIATIONS = frozenset(
    {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "mt", "vs", "approx", "fig", "cf", "al"}
)
_OPENERS = "\"'([{“‘«"
_PRONOUN_I = "I"


def split_sentences(text: str, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    """Split text into sentences, none longer than `max_chars` characters.

    Args:
        text: Plain text, usually the output of `clean_for_speech`. Runs of
            whitespace (newlines included) are collapsed to single spaces.
        max_chars: The longest chunk allowed.

    Returns:
        The chunks in order, stripped, with no empty strings. An empty list
        when the text has nothing but whitespace.

    Raises:
        ValueError: If `max_chars` is less than 1.
    """
    if max_chars < 1:
        raise ValueError(f"max_chars must be at least 1, got {max_chars}")
    text = " ".join(text.split())
    chunks: list[str] = []
    for sentence in _split_at_sentence_ends(text):
        chunks.extend(_wrap_long_sentence(sentence, max_chars))
    return chunks


def _split_at_sentence_ends(text: str) -> list[str]:
    """Split whitespace-normalised text after each real sentence ending."""
    sentences = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        if _is_abbreviation(text, match):
            continue
        sentences.append(text[start : match.end()].strip())
        start = match.end()
    sentences.append(text[start:].strip())
    return [sentence for sentence in sentences if sentence]


def _is_abbreviation(text: str, match: re.Match[str]) -> bool:
    """Say whether a lone full stop belongs to an abbreviation, not a sentence."""
    if match.group() != ".":
        return False
    word = text[: match.start()].rsplit(" ", 1)[-1].lstrip(_OPENERS)
    if word.lower() in _TITLE_ABBREVIATIONS:
        return True
    # "I." is far more often the pronoun ending a sentence than an initial.
    if word == _PRONOUN_I:
        return False
    return _DOTTED_ABBREVIATION.fullmatch(word + ".") is not None


def _wrap_long_sentence(sentence: str, max_chars: int) -> list[str]:
    """Break one sentence into pieces of at most `max_chars` characters."""
    pieces = []
    rest = sentence
    while len(rest) > max_chars:
        cut = _best_cut(rest, max_chars)
        pieces.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        pieces.append(rest)
    return pieces


def _best_cut(text: str, max_chars: int) -> int:
    """Pick where to cut an over-long sentence so the head fits `max_chars`.

    Prefers the last clause break (comma, semicolon, colon, dash) that isn't
    too early, then the last space, then a hard cut at the limit.
    """
    # One extra character, so a space sitting right at the limit counts.
    window = text[: max_chars + 1]
    clause_cuts = [m.end() for m in _CLAUSE_BREAK.finditer(window) if m.end() <= max_chars]
    if clause_cuts and clause_cuts[-1] >= max_chars * MIN_CLAUSE_FRACTION:
        return clause_cuts[-1]
    last_space = window.rfind(" ")
    if last_space > 0:
        return last_space
    return max_chars
