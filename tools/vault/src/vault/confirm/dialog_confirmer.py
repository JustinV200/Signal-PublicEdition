"""`DialogConfirmer`: the v1 `Confirmer`, an Allow/Deny dialog naming the credential and origin.

The dialog itself is the shared signal_confirm one (packages/confirm): Deny is
the default, Allow has no keyboard shortcut, and it denies by itself on timeout.
"""

from collections.abc import Awaitable, Callable

from signal_confirm import confirm_async, sanitize_text

from vault.confirm.base import ConfirmRequest

CONFIRM_TIMEOUT_S = 60.0
DIALOG_TITLE = "Signal vault: allow sign-in?"
MAX_SHOWN_CHARS = 120

# (title, message, *, timeout_s) -> approved? The real one is signal_confirm.confirm_async.
AskOwner = Callable[..., Awaitable[bool]]


def _printable(text: str) -> str:
    """Flatten `text` to one capped line (see signal_confirm.sanitize_text).

    The name comes from store.json, which isn't verified until after this prompt,
    so it must not be able to fake extra lines, pad text out of view, or reorder
    the origin.
    """
    return sanitize_text(text, MAX_SHOWN_CHARS)


def confirm_text(request: ConfirmRequest, timeout_s: float) -> str:
    """Build the dialog body for `request`."""
    lines = [
        "Claude wants the vault to sign in.",
        "",
        f"Credential: {_printable(request.credential_name)} ({_printable(request.credential_id)})",
        f"Site origin: {_printable(request.top_origin)}",
    ]
    if request.frame_origin != request.top_origin:
        lines.append(f"Login frame origin: {_printable(request.frame_origin)}")
    lines += [
        "",
        "Only click Allow if you expect this sign-in and the origin is right.",
        f"Deny is the default. This denies itself after {int(timeout_s)} seconds.",
    ]
    return "\n".join(lines)


class DialogConfirmer:
    """Confirms each fill with a topmost Allow/Deny dialog; Deny is the default and the timeout."""

    def __init__(self, ask: AskOwner = confirm_async, timeout_s: float = CONFIRM_TIMEOUT_S) -> None:
        """Create the confirmer.

        Args:
            ask: The async prompt (signal_confirm.confirm_async by default).
            timeout_s: Seconds before the prompt denies by itself.
        """
        self._ask = ask
        self._timeout_s = timeout_s

    async def confirm(self, request: ConfirmRequest) -> bool:
        """Ask the owner and return True only for an explicit Allow."""
        text = confirm_text(request, self._timeout_s)
        return await self._ask(DIALOG_TITLE, text, timeout_s=self._timeout_s)
