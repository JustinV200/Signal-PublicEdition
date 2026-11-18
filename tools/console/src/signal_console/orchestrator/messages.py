"""The words the console sends the orchestrator, and the matching line shown in the console.

Typed text becomes a plain-language request the orchestrator carries out with
its own tools (buttons don't: the server runs them, see signal_console.actions).
Each starts with MARKER and the owner's name (SIGNAL_OWNER_NAME in .env, see
signal_console.owner), since the inbox shows no sender name. MARKER is a
label only, never proof of consent: any process holding the session's inbox
token can write the same words.
"""

from dataclasses import dataclass
from typing import Any

from signal_console.owner import read_owner_name
from signal_console.paths import ENV_FILE_PATH

MARKER = "[Signal console]"
MAX_TEXT_CHARS = 20_000


class RequestError(ValueError):
    """The text can't be sent (not a string, blank or too long)."""


@dataclass(frozen=True)
class ConsoleRequest:
    """One thing the owner asked for in the console.

    Attributes:
        display_text: The "you" line the console shows.
        orchestrator_text: What the orchestrator's inbox receives.
    """

    display_text: str
    orchestrator_text: str


def chat_request(text: Any) -> ConsoleRequest:
    """A message the owner typed.

    Raises:
        RequestError: Not a string, blank, or longer than MAX_TEXT_CHARS.
        OSError: The repo's .env exists but can't be read (its first read only).
    """
    if not isinstance(text, str) or not text.strip():
        raise RequestError("text must be a non-empty string")
    if len(text) > MAX_TEXT_CHARS:
        raise RequestError(f"text is longer than {MAX_TEXT_CHARS} characters")
    return ConsoleRequest(text, f"{MARKER} {read_owner_name(ENV_FILE_PATH)}: {text}")
