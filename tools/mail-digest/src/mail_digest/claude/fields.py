"""Validators for single fields of the model's structured output.

The model writes these after reading untrusted email, so each one is checked
strictly or rewritten into a safe form before the runner stores, logs or speaks it.
"""

import re

from mail_digest.settings import MAX_SENTENCE_CHARS

MAX_SLUG_CHARS = 80
NOT_SLUG = re.compile(r"[^a-z0-9]+")
# Gmail message ids, as the mail tool returns them (hex).
MESSAGE_ID = re.compile(r"[0-9a-f]{8,32}")
# A bare address, not "Name <address>".
EMAIL = re.compile(r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,63}(\.[A-Za-z0-9-]{1,63}){1,8}")
URL = re.compile(r"https?://\S*|www\.\S*", re.IGNORECASE)
# Markdown and markup characters a voice shouldn't read out.
UNSPOKEN = re.compile(r"[`*#|<>\[\]]")
SENTENCE_ENDINGS = (".", "!", "?")
SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")
# Spoken sentences an email may have planted: a bare domain (evil.example) or an @
# could send the owner somewhere, and a long number is likely a code or account number.
DOMAIN = re.compile(r"\b[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}\b", re.IGNORECASE)
LONG_NUMBER = re.compile(r"\d{6,}")
# A sentence is cut to this before the regexes run: DOMAIN takes quadratic time on
# a long "a-a-a-..." run, and only MAX_SENTENCE_CHARS of it can be spoken anyway.
MAX_INPUT_CHARS = 4 * MAX_SENTENCE_CHARS


def slugify(text: str) -> str:
    """Lowercase a-z0-9 words joined by "-", at most MAX_SLUG_CHARS ("" if nothing is left)."""
    return NOT_SLUG.sub("-", text.casefold()).strip("-")[:MAX_SLUG_CHARS].strip("-")


def clean_sentence(text: str) -> str:
    """Speakable text, ending in punctuation, or "" if nothing speakable is left.

    Only the first MAX_INPUT_CHARS are read. URLs, markup and control characters
    are stripped. Each sentence with a domain, an @ or a 6+ digit number (spaces
    ignored) is dropped, and what's left is cut at a word break to at most
    MAX_SENTENCE_CHARS.
    """
    text = text[:MAX_INPUT_CHARS]
    text = " ".join(UNSPOKEN.sub("", URL.sub("", text)).split())
    text = "".join(ch for ch in text if ch.isprintable())
    text = " ".join(s for s in SENTENCE_BREAK.split(text) if _is_safe_to_speak(s))
    if len(text) > MAX_SENTENCE_CHARS:
        text = text[: MAX_SENTENCE_CHARS + 1].rsplit(" ", 1)[0].rstrip(",;:- ")
    text = text.strip()
    if text and not text.endswith(SENTENCE_ENDINGS):
        text += "."
    return text


def _is_safe_to_speak(sentence: str) -> bool:
    """True unless the sentence has a domain, an @ or a long number (see DOMAIN)."""
    return (
        "@" not in sentence
        and DOMAIN.search(sentence) is None
        and LONG_NUMBER.search(sentence.replace(" ", "")) is None
    )


def is_message_id(text: str) -> bool:
    """True for a Gmail message id."""
    return MESSAGE_ID.fullmatch(text) is not None


def is_email(text: str) -> bool:
    """True for one bare email address."""
    return EMAIL.fullmatch(text) is not None
