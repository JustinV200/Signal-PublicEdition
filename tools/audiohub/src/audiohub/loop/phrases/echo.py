"""Echo detection: did the mic just hear Claude's own speech?

The glasses mic can pick up Claude's voice, which Whisper then transcribes,
e.g. "go ahead and delete them", which would read as a reply. Three checks,
by when the utterance began:

- While Claude is audible (barge-in, until the user could have heard it
  stop): `is_echo_during_speech` compares it with the sentences Claude said
  around then, loosely, as a bag of words: a short transcript is an echo when
  every word of it was spoken. That keeps Claude's own "...so stop there" or
  "Claude here" from reading as a stop command or a wake phrase, since a
  false stop costs far more than an ignored one.
- In the rest of the echo tail (barge-in, the user has heard Claude stop and
  may be replying): `is_echo_of_ending`. An echo then is a run of Claude's
  words in order, ending where Claude stopped, so a transcript counts as one
  only when it lines up with the end of what Claude said. Matching words that
  come earlier or in another order are the user answering in Claude's terms
  ("go ahead", "do it"), and so is a leading "yes" or "no" Claude didn't
  say there. Common words prove little, so a transcript with fewer than two
  content words must be exactly Claude's last words.
- After the echo tail: `is_echo`, the original check: 3+ words, mostly from
  Claude's last few, in any order. With barge-in off (the mic was muted until
  then) it is the only check. With barge-in on it still decides alone for a
  stop or a wake phrase, but Claude's voice has stopped
  reaching the mic by then, so any other transcript must also pass
  `is_exact_ending`: word for word Claude's last words.

The first two forgive the ways Whisper mishears Claude: wake-word soundalikes
("Clawed") count as the wake word, and a heard word of 4+ letters matches a
spoken word it starts ("stop", "stopped").
"""

from .tokens import words
from .wake import canonical_words
from .yes_no import is_yes_or_no_word

# A transcript heard after the echo tail needs this many words to be called an
# echo: a real one-word "yes" right after Claude said "yes" must still count
# as the user's answer. Over Claude, a shorter one must match every word.
MIN_ECHO_WORDS = 3
# Share of the transcript's words that must appear in Claude's speech.
MIN_ECHO_OVERLAP = 0.75
# Claude's last words compared against are the transcript's length plus this
# many, so a few words Whisper missed still fit.
TAIL_SLACK_WORDS = 4
# A heard word this long or longer also matches a spoken word it starts:
# Whisper hears Claude's "stopped" as "stop".
MIN_PREFIX_LETTERS = 4
# Fewer content words than this and the transcript must be exactly Claude's
# last words: "do it" or "yes" alone could be anyone's.
MIN_CONTENT_WORDS = 2

# Words too common to show that a transcript repeats Claude, compared after
# tokens.py drops apostrophes ("I'll" -> "ill"). Reply words ("yes", "no",
# "okay") are left out on purpose: they are what the user answers with.
COMMON_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "so", "if", "then", "than", "as",
        "i", "me", "my", "you", "your", "we", "us", "our", "they", "them", "their",
        "he", "him", "his", "she", "her", "it", "its", "this", "that", "these",
        "those", "there", "here", "what", "which", "who", "how",
        "is", "are", "was", "were", "be", "been", "am", "im", "ill", "ive", "id",
        "youre", "youll", "thats", "dont", "lets", "do", "does", "did", "have",
        "has", "had", "will", "would", "can", "could", "should", "shall", "may",
        "might", "must", "to", "of", "in", "on", "at", "for", "with", "from", "by",
        "about", "up", "out", "not", "just", "now", "one", "all", "some", "any",
    }
)  # fmt: skip


def is_echo(transcript: str, last_spoken: str) -> bool:
    """Say whether a transcript looks like the mic re-hearing Claude's last words, after the tail.

    The original check, kept as it was: a bag of words, so word order
    doesn't matter, and the 75% share forgives a word Whisper misheard.

    Args:
        transcript: What Whisper heard after Claude's speech and its tail.
        last_spoken: The text Claude last spoke (the whole batch).

    Returns:
        True if the transcript has at least MIN_ECHO_WORDS words and at least
        MIN_ECHO_OVERLAP of them appear in the last words of `last_spoken`
        (as many as the transcript has, plus TAIL_SLACK_WORDS).
    """
    heard = words(transcript)
    if len(heard) < MIN_ECHO_WORDS:
        return False
    spoken_tail = set(words(last_spoken)[-(len(heard) + TAIL_SLACK_WORDS) :])
    return sum(1 for word in heard if word in spoken_tail) / len(heard) >= MIN_ECHO_OVERLAP


def is_echo_of_ending(transcript: str, spoken: str) -> bool:
    """Say whether a transcript is the last words of `spoken`, as an echo would be.

    With fewer than MIN_CONTENT_WORDS content words (words not in
    COMMON_WORDS), every word must match Claude's last words in order.
    Otherwise the content words must line up with Claude's last content
    words, in order, with at most a quarter of them misheard, missed or extra,
    though a leading yes/no word Claude didn't say right there is never
    forgiven. Words are compared after canonical_words(), and a heard word of
    MIN_PREFIX_LETTERS or more also matches a spoken word it starts.

    Args:
        transcript: What Whisper heard.
        spoken: What Claude said, ending where its audio ended.

    Returns:
        True for an echo of the end of `spoken`; False for a transcript with
        no words or nothing spoken.
    """
    heard = canonical_words(transcript)
    said = canonical_words(spoken)
    if not heard or not said:
        return False
    content = _content_words(heard)
    if len(content) < MIN_CONTENT_WORDS:
        return _ending_errors(heard, said) == 0
    said_content = _content_words(said)
    errors = _ending_errors(content, said_content)
    if errors > int(len(content) * (1 - MIN_ECHO_OVERLAP)):
        return False
    # "Yes, delete the old logs." after "...delete the old logs?" is the user
    # answering, not Whisper adding a word: a leading yes/no word that Claude's
    # ending doesn't account for is never one of the forgiven errors.
    is_leading_answer = is_yes_or_no_word(content[0])
    return not (is_leading_answer and errors > _ending_errors(content[1:], said_content))


def is_exact_ending(transcript: str, spoken: str) -> bool:
    """Say whether a transcript is word for word the last words of `spoken`.

    The strict check for a reply after the echo tail, with barge-in on: only
    case and punctuation are ignored, so one extra, missed or misheard word
    ("Please delete the old logs." after "...delete the old logs?") makes it
    a reply.

    Args:
        transcript: What Whisper heard.
        spoken: What Claude said.

    Returns:
        True if the transcript's words are the last words of `spoken`; False
        for a transcript with no words.
    """
    heard = words(transcript)
    return bool(heard) and words(spoken)[-len(heard) :] == heard


def is_echo_during_speech(transcript: str, recently_spoken: str) -> bool:
    """Say whether a transcript heard while Claude was talking is just Claude's own voice.

    Args:
        transcript: What Whisper heard while Claude was audible.
        recently_spoken: The sentences Claude said around that time.

    Returns:
        True if every word of the transcript appears in `recently_spoken`, or
        if it has at least MIN_ECHO_WORDS words and at least MIN_ECHO_OVERLAP
        of them do. Words are compared after canonical_words(), and a heard
        word of MIN_PREFIX_LETTERS or more also matches a spoken word it
        starts. False for a transcript with no words.
    """
    heard = canonical_words(transcript)
    if not heard:
        return False
    spoken = set(canonical_words(recently_spoken))
    overlap = sum(1 for word in heard if _was_spoken(word, spoken)) / len(heard)
    return overlap == 1.0 or (len(heard) >= MIN_ECHO_WORDS and overlap >= MIN_ECHO_OVERLAP)


def _ending_errors(heard: list[str], spoken: list[str]) -> int:
    """The fewest word errors that turn `heard` into the last words of `spoken`.

    An error is a misheard, extra or missed word: a word-level edit distance
    in which the run of spoken words may start anywhere but must end with the
    last spoken word, because an echo stops where Claude's audio stopped.
    """
    spoken = spoken[-(len(heard) + TAIL_SLACK_WORDS) :]
    # previous[j]: errors for the heard words so far against a run ending at
    # spoken word j. With no heard words yet, an empty run anywhere is free.
    previous = [0] * (len(spoken) + 1)
    for heard_count, word in enumerate(heard, start=1):
        current = [heard_count] + [0] * len(spoken)
        for j, said in enumerate(spoken, start=1):
            current[j] = min(
                previous[j - 1] + (0 if _matches(word, said) else 1),
                previous[j] + 1,  # Whisper added a word
                current[j - 1] + 1,  # Whisper missed a word
            )
        previous = current
    return previous[-1]


def _content_words(text_words: list[str]) -> list[str]:
    return [word for word in text_words if word not in COMMON_WORDS]


def _matches(heard: str, said: str) -> bool:
    """Whether a heard word is a spoken one, exactly or (if long enough) as its start."""
    return heard == said or (len(heard) >= MIN_PREFIX_LETTERS and said.startswith(heard))


def _was_spoken(word: str, spoken: set[str]) -> bool:
    """Whether `word` matches any spoken word."""
    return word in spoken or any(_matches(word, other) for other in spoken)
