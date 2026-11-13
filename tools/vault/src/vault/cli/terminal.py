"""Terminal guards for the owner CLI: refuse non-interactive stdin, read hidden values twice.

Management commands must be typed by the owner in their own terminal. If
stdin isn't an interactive TTY (piped, redirected, or run by an agent's shell),
they refuse before reading anything, so a secret can't be piped in and an add
can't be scripted. Native Windows Python sees Git Bash/mintty as a pipe; use
Windows Terminal, PowerShell or cmd.
"""

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes
from typing import TextIO


class CliError(Exception):
    """A problem the owner can fix; printed as one line, never with a traceback."""


NOT_A_TTY_MESSAGE = (
    "refusing: stdin is not an interactive terminal. Run this yourself in Windows Terminal, "
    "PowerShell or cmd (not piped, not from an agent, not Git Bash)."
)


def has_console_mode(stream: TextIO) -> bool:
    """On Windows, return True only if `stream` is a real console (GetConsoleMode succeeds).

    Needed because Windows reports isatty() True for the NUL device, so
    `vault remove x < NUL` would otherwise pass. GetConsoleMode fails for NUL,
    pipes and files. Always True elsewhere, where isatty() is reliable.
    """
    if sys.platform != "win32":
        return True
    import msvcrt

    try:
        handle = msvcrt.get_osfhandle(stream.fileno())
    except (AttributeError, OSError, ValueError):
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetConsoleMode.restype = wintypes.BOOL
    mode = wintypes.DWORD()
    return bool(kernel32.GetConsoleMode(handle, ctypes.byref(mode)))


def require_interactive_stdin(stdin: TextIO) -> None:
    """Raise CliError unless `stdin` is an interactive terminal (and, on Windows, a console).

    Raises:
        CliError: stdin is piped, redirected (including from NUL) or closed.
    """
    try:
        is_terminal = stdin.isatty()
    except (AttributeError, ValueError):
        is_terminal = False
    if not (is_terminal and has_console_mode(stdin)):
        raise CliError(NOT_A_TTY_MESSAGE)


def read_hidden_twice(read_secret: Callable[[str], str], label: str, *, allow_empty: bool) -> str:
    """Read a hidden value twice and return it if both entries match.

    Args:
        read_secret: A no-echo prompt such as getpass.getpass.
        label: What is being asked for, e.g. "Password".
        allow_empty: Accept an empty value.

    Returns:
        The value.

    Raises:
        CliError: The entries differ, or the value is empty when not allowed.
    """
    first = read_secret(f"{label}: ")
    second = read_secret(f"{label} again: ")
    if first != second:
        raise CliError(f"the two {label.lower()} entries didn't match")
    if not first and not allow_empty:
        raise CliError(f"{label.lower()} can't be empty")
    return first
