"""Terminal prompts with defaults: Enter takes the default, 's' skips. Used by every UI part.

Colour is only ever an extra: every state also has a word or symbol, so nothing
depends on telling colours apart.
"""

import os
import sys

DIM, BOLD, RESET = "\033[2m", "\033[1m", "\033[0m"


def _use_ansi() -> bool:
    """True when stdout is a terminal that takes ANSI codes (and NO_COLOR isn't set)."""
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def style(text: str, code: str) -> str:
    """`text` wrapped in an ANSI code when the terminal supports it."""
    return f"{code}{text}{RESET}" if _use_ansi() else text


class TerminalAsker:
    """Asks the user at the terminal. Satisfies steps.Asker."""

    interactive = True

    def say(self, text: str) -> None:
        """Print a line."""
        print(text)

    def confirm(self, question: str, default: bool) -> bool:
        """Yes/no with a default. 's' (skip) counts as no."""
        hint = "[Y/n/s=skip]" if default else "[y/N/s=skip]"
        while True:
            answer = input(f"{question} {hint} ").strip().lower()
            if not answer:
                return default
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no", "s", "skip"):
                return False
            print("Type y, n or s.")

    def text(self, question: str) -> str | None:
        """A typed value; empty input means skip (None). Never used for passwords."""
        answer = input(f"{question} (Enter to skip): ").strip()
        return answer or None


def pause(message: str = "Press Enter to continue, or q to stop: ") -> bool:
    """Wait for Enter. Returns False if the user typed q."""
    return input(message).strip().lower() != "q"
